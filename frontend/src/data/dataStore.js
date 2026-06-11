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
const refreshOf = (id) =>
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

  meta: (id) => {
    const b = (window.bancoById && window.bancoById(id)) || {};
    return {
      table: tableOf(id),
      refresh: refreshOf(id),
      version: (goldVersion[id] && goldVersion[id].v) || null,
      source: b.source,
      scope: b.scope,
      domain: b.domain,
      cobertura: b.cobertura || null,
      maturity: b.maturity,
      maturityDate: b.maturity === 'estavel' ? null : b.maturityDate || b.plannedRelease || null,
      prov: b.prov || null,
    };
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
