// dataStore.js — API-backed pushdown query boundary. Replaces the prototype's
// synthetic proto/dataStore.js, re-exposing the SAME window.dataStore interface
// (status/get/isStale/subscribe/load/meta/…) the reused views + DataBoundary
// call. The only change is the body of load(): instead of reading synthetic
// globals it FETCHES /api/snapshot (the Flask BFF → parameterized BigQuery,
// memoized by flask-caching) and decorates the result with the client-side
// registries the API deliberately omits (UF tile col/row, quality label/color).
//
// Conventions: currency × correction pick the deflated value column SERVER-side
// (the scientific core), so the snapshot is fetched per-convention and cached by
// banco|currency|correction. The boot bridges convention changes via
// setConventions() (see main.jsx) — DataBoundary.load(bancoId) itself passes no
// conv, so we keep the active one here.

import { decorateSnapshot } from './decorate';

const API = '/api';

const store = {}; // bancoId -> { status, version, loadedAt, data, error }
const subs = new Set();
const notify = () => {
  for (const fn of subs) {
    try {
      fn();
    } catch {
      /* keep other subscribers alive */
    }
  }
};

// Active display conventions (currency/correction drive the value column).
let activeConv = { currency: 'BRL', correction: 'IPCA' };
const convKey = () => `${activeConv.currency}|${activeConv.correction}`;
const cacheKey = (id) => `${id}|${convKey()}`;

// Provenance/version metadata as the backend would report it. Kept as the
// prototype had it (static facts + banco-registry fallbacks); the live refresh
// timestamp can later come from /api/source-meta. Drives bancoMeta()/the page hero.
const goldVersion = {
  ibge_pevs: { v: 'pevs-2024.1' },
  mdic_comex: { v: 'comex-2024.12' },
  un_comtrade: { v: 'comtrade-2024.1' },
  ibge_pam: { v: 'pam-2024.1' },
  sefaz_nf: { v: 'nfe-preview', at: '—' },
};
const goldTable = {
  ibge_pevs: 'gold_pevs_production',
  mdic_comex: 'gold_comex_flows',
  un_comtrade: 'gold_comtrade_flows',
  ibge_pam: 'gold_pam_production',
  sefaz_nf: 'gold_nfe_flows',
};
const tableOf = (id) => goldTable[id] || null;

// Live provenance from /api/source-meta (gold_source_metadata), fetched per banco
// and cached. This is what makes the hero / Sobre / Saúde provenance + coverage
// denominators track the REAL Gold (last_refresh, year_start/end, total_rows,
// products_total, ufs_total) instead of the frozen bancos.js literals — the seam
// existed, the frontend just never called it. Falls back to the registry prov
// until it resolves (or for a source with no Gold row yet).
const sourceMeta = {}; // bancoId -> serialize_source_meta payload (or {} when absent)

function fetchSourceMeta(id) {
  return fetch(`${API}/source-meta?banco=${encodeURIComponent(id)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((m) => {
      if (m && typeof m === 'object') {
        sourceMeta[id] = m;
        notify(); // re-render the hero/Sobre/Saúde with the real values
      }
    })
    .catch(() => {
      /* provenance is non-critical: keep the registry fallback, never block load() */
    });
}

const refreshOf = (id) =>
  (sourceMeta[id] && sourceMeta[id].lastRefreshLabel) ||
  (goldVersion[id] && goldVersion[id].at) ||
  (window.bancoById && window.bancoById(id)?.prov?.refresh) ||
  null;

// The core BancoSnapshot fields (contracts.js) + their expected JS type. Their
// presence distinguishes a real snapshot from an error payload or a drifted
// backend shape — so a contract change surfaces as a CLEAR error, not a silent
// empty view (every downstream producer reads these and would just render blank).
const SNAPSHOT_SHAPE = [
  ['products', Array.isArray],
  ['productTS', (v) => !!v && typeof v === 'object' && !Array.isArray(v)],
  ['overviewTS', Array.isArray],
  ['ufData', Array.isArray],
  ['quality', Array.isArray],
];

function assertSnapshotShape(snap) {
  if (!snap || typeof snap !== 'object' || Array.isArray(snap)) {
    throw new Error('Resposta de /api/snapshot inesperada (não é um objeto BancoSnapshot).');
  }
  const bad = SNAPSHOT_SHAPE.filter(([k, ok]) => !ok(snap[k])).map(([k]) => k);
  if (bad.length) {
    throw new Error(`Resposta de /api/snapshot fora do contrato (campos inválidos: ${bad.join(', ')}).`);
  }
}

async function fetchSnapshot(id) {
  const qs = new URLSearchParams({
    banco: id,
    currency: activeConv.currency,
    correction: activeConv.correction,
  });
  const r = await fetch(`${API}/snapshot?${qs}`);
  if (!r.ok) throw new Error(`Falha ao consultar a Gold no BigQuery (HTTP ${r.status}).`);
  const snap = await r.json();
  assertSnapshotShape(snap); // fail loudly on a drifted contract, don't render blank
  snap.table = tableOf(id);
  return decorateSnapshot(snap);
}

window.dataStore = {
  status: (id) => (store[cacheKey(id)] && store[cacheKey(id)].status) || 'idle',
  version: (id) => (store[cacheKey(id)] && store[cacheKey(id)].version) || null,
  loadedAt: (id) => (store[cacheKey(id)] && store[cacheKey(id)].loadedAt) || null,
  get: (id) => (store[cacheKey(id)] && store[cacheKey(id)].data) || null,
  error: (id) => (store[cacheKey(id)] && store[cacheKey(id)].error) || null,
  latestVersion: (id) => (goldVersion[id] && goldVersion[id].v) || null,
  latestAt: (id) => refreshOf(id),
  table: (id) => tableOf(id),

  // Live provenance for a banco. The numeric coverage (rows, products, UFs, year
  // span) + the last-refresh stamp are overlaid from /api/source-meta when it has
  // resolved, so every consumer (hero counters + denominators, Sobre, Saúde) reads
  // the REAL Gold instead of the registry literal. The registry prov is the
  // pre-resolution / no-Gold-row fallback.
  meta: (id) => {
    const b = (window.bancoById && window.bancoById(id)) || {};
    const sm = sourceMeta[id] || null;
    const prov = b.prov ? { ...b.prov } : sm ? {} : null;
    if (sm && prov) {
      if (sm.totalRows != null) prov.totalRows = sm.totalRows;
      if (sm.productsTotal != null) prov.productsTotal = sm.productsTotal;
      if (sm.ufsTotal != null) prov.ufsTotal = sm.ufsTotal;
      if (sm.yearStart != null) prov.yearStart = sm.yearStart;
      if (sm.yearEnd != null) prov.yearEnd = sm.yearEnd;
      if (sm.yearStart != null && sm.yearEnd != null) prov.yearsTotal = sm.yearEnd - sm.yearStart + 1;
      if (sm.lastRefreshLabel) prov.refresh = sm.lastRefreshLabel;
      // Keep the registry "última safra" label but track the real latest year.
      if (sm.yearEnd != null && typeof prov.lastCrop === 'string') {
        prov.lastCrop = prov.lastCrop.replace(/\d{4}/, String(sm.yearEnd));
      }
    }
    return {
      table: (sm && sm.table) || tableOf(id),
      refresh: refreshOf(id),
      version: (goldVersion[id] && goldVersion[id].v) || null,
      coverage: sm
        ? {
            yearStart: sm.yearStart,
            yearEnd: sm.yearEnd,
            totalRows: sm.totalRows,
            productsTotal: sm.productsTotal,
            ufsTotal: sm.ufsTotal,
          }
        : null,
      source: b.source,
      scope: b.scope,
      domain: b.domain,
      cobertura: b.cobertura || null,
      maturity: b.maturity,
      maturityDate: b.maturity === 'estavel' ? null : b.maturityDate || b.plannedRelease || null,
      prov,
    };
  },

  // Fetch ONLY the live provenance (/api/source-meta) for a banco, without the
  // heavy per-convention snapshot pushdown. Lets a provenance-only surface (Saúde,
  // reached directly via ?ip=health without any data view loading first) show the
  // REAL Gold metadata instead of the registry fallback. Deduped: a banco whose
  // meta already resolved is a no-op. Pair with subscribe() to re-render on resolve.
  loadMeta(id) {
    if (sourceMeta[id]) return Promise.resolve(sourceMeta[id]);
    return fetchSourceMeta(id);
  },

  isStale: (id) =>
    !!(
      store[cacheKey(id)] &&
      store[cacheKey(id)].status === 'ready' &&
      goldVersion[id] &&
      store[cacheKey(id)].version !== goldVersion[id].v
    ),

  subscribe(fn) {
    subs.add(fn);
    return () => subs.delete(fn);
  },

  // Run (or re-run) a banco's pushdown query and cache the decorated result.
  load(id) {
    const key = cacheKey(id);
    // Fetch live provenance once per banco (independent of the per-convention
    // snapshot cache), so the hero/Sobre/Saúde show real Gold metadata.
    if (!sourceMeta[id]) fetchSourceMeta(id);
    const cur = store[key];
    if (cur && cur.status === 'ready' && !this.isStale(id)) return Promise.resolve(cur);
    if (cur && cur.status === 'loading') return Promise.resolve(cur);
    store[key] = { status: 'loading', version: null, loadedAt: null, data: null, error: null };
    notify();
    return fetchSnapshot(id)
      .then((data) => {
        store[key] = {
          status: 'ready',
          version: (goldVersion[id] && goldVersion[id].v) || `${id}-live`,
          loadedAt: refreshOf(id) || 'agora',
          data,
          error: null,
        };
        notify();
        return store[key];
      })
      .catch((err) => {
        store[key] = {
          status: 'error',
          version: null,
          loadedAt: null,
          data: null,
          error: err?.message || 'Erro ao carregar dados.',
        };
        notify();
        return store[key];
      });
  },

  // Boot bridge: the app calls this when the conventions change. Switching the
  // currency/correction means a different deflated value column → re-fetch. We
  // just update the active conv + notify; subscribed DataBoundaries re-render
  // and call load(id), which now hits the new convention's cache key.
  setConventions(conv) {
    if (!conv) return;
    const next = { currency: conv.currency || 'BRL', correction: conv.correction || 'IPCA' };
    if (next.currency === activeConv.currency && next.correction === activeConv.correction) return;
    activeConv = next;
    notify();
  },

  // Re-run the active query (used by the freshness "Recarregar" + error retry).
  reload(id) {
    delete store[cacheKey(id)];
    return this.load(id);
  },
};
