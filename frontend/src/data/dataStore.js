// dataStore.js — API-backed pushdown query boundary. Replaces the prototype's
// synthetic data store, re-exposing the SAME window.dataStore interface
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
// Per-cache-key monotonic fetch generation. A same-key reload (or a convention
// flip that re-runs load for an already-loading key) can start a NEWER fetch
// while an older one is still in flight; without this token the older response
// (resolving last) could overwrite the newer one. We capture the generation at
// fetch start and ignore a resolution whose token is stale (FINDING M8).
const loadGen = {}; // cacheKey -> number (latest started generation)
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
// Active flow (export/import) — a SERVER-SIDE filter, NOT a display convention: the
// trade marts are pre-aggregated over flow, so a direction is part of the snapshot's
// cache key + request, exactly like the value column. 'all' (the default) sums every
// flow, so a production banco (no flow) and an unfiltered trade request are unchanged.
let activeFlow = 'all';
const convKey = () => `${activeConv.currency}|${activeConv.correction}|${activeFlow}`;
const cacheKey = (id) => `${id}|${convKey()}`;

// The Gold table name is NOT duplicated here. Single source of truth: the live
// /api/source-meta payload (gold_source_metadata.gold_table); the banco registry
// `table` field is the only static fallback (a planejado banco with no Gold table
// resolves to null → "ainda não publicada"). No hardcoded version map — there is
// no live version/staleness signal yet, so freshness is reported honestly (never
// "stale" from a fabricated version).
const tableOf = (id) => (window.bancoById && window.bancoById(id)?.table) || null;

// Live provenance from /api/source-meta (gold_source_metadata), fetched per banco
// and cached. This is what makes the hero / Sobre / Saúde provenance + coverage
// denominators track the REAL Gold (last_refresh, year_start/end, total_rows,
// products_total, ufs_total) instead of the frozen bancos.js literals — the seam
// existed, the frontend just never called it. Falls back to the registry prov
// until it resolves (or for a source with no Gold row yet).
const sourceMeta = {}; // bancoId -> serialize_source_meta payload (or {} when absent)
// In-flight /source-meta requests, keyed by banco. fetchSourceMeta only sets
// sourceMeta[id] AFTER the request resolves, so concurrent callers (load() +
// loadMeta() from ViewHealth/ViewAbout, a re-render, React StrictMode's double
// effect) would each pass the `!sourceMeta[id]` guard and fire a DUPLICATE
// request before the first lands. Sharing the in-flight promise dedupes them to
// exactly one network call per banco (FINDING #8).
const sourceMetaInFlight = {}; // bancoId -> Promise

// Overlay the live, operator-editable maturity/coverage (/api/source-meta, merged
// from research_inputs.banco_metadata) onto the in-memory registry banco, so the
// the UI's MaturityTag / MaturityBanner / coverage — which read the static banco —
// reflect a Console flip (e.g. beta→estavel) WITHOUT a rebuild+redeploy. Sparse:
// each field is overlaid only when the backend sends a non-null value; otherwise the
// bancos.js literal stands (the backend default IS that literal). maturityMeta(banco)
// then resolves the live stage app-wide; notify() re-renders.
function overlayBancoMetadata(id, m) {
  const b = window.bancoById && window.bancoById(id);
  if (!b) return;
  if (m.maturity) b.maturity = m.maturity;
  if (m.maturityNote != null) b.maturityNote = m.maturityNote;
  if (m.maturityDate != null) b.maturityDate = m.maturityDate;
  if (m.cobertura && typeof m.cobertura === 'object') b.cobertura = m.cobertura;
}

function fetchSourceMeta(id) {
  if (sourceMetaInFlight[id]) return sourceMetaInFlight[id];
  const p = fetch(`${API}/source-meta?banco=${encodeURIComponent(id)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((m) => {
      if (m && typeof m === 'object') {
        sourceMeta[id] = m;
        overlayBancoMetadata(id, m); // live maturity/coverage → registry banco
      } else {
        // HTTP error / empty: record an EMPTY resolution so hasMeta() turns true
        // and the DataGate stops waiting (degrades to "—"/placeholder rather than
        // an infinite spinner). Source-meta is the only maturity source now.
        sourceMeta[id] = sourceMeta[id] || {};
      }
      notify(); // re-render the hero/Sobre/Saúde with the real values (or the fallback)
    })
    .catch(() => {
      // Network failure: same honest degrade — mark attempted so the gate proceeds.
      sourceMeta[id] = sourceMeta[id] || {};
      notify();
    })
    .finally(() => {
      delete sourceMetaInFlight[id]; // allow a future refresh once this settles
    });
  sourceMetaInFlight[id] = p;
  return p;
}

// The Gold refresh stamp comes SOLELY from the live /api/source-meta payload —
// no fabricated fallback (the registry prov no longer carries a refresh).
const refreshOf = (id) =>
  (sourceMeta[id] && sourceMeta[id].lastRefreshLabel) || null;

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

// Nested-ROW contracts (contracts.js): the top-level check above only proves the
// COLLECTIONS exist, so a backend field RENAME inside a row (e.g. productTS `q` →
// `quantity`) would slip through and silently blank a chart. When a collection is
// non-empty, assert its first row carries the keys downstream reads. Empty
// collections skip the check (no row to inspect), so a legitimately empty banco
// still validates. The keys here are the load-bearing ones serializers.py emits.
const ROW_SHAPE = [
  ['overviewTS', ['y', 'v']],
  ['quality', ['id', 'count']],
  ['productTS', ['y', 'v']],
];

// First data row of a collection: arrays → [0]; productTS (object keyed by code)
// → the first series' first point.
function firstRow(coll) {
  if (Array.isArray(coll)) return coll[0];
  if (coll && typeof coll === 'object') {
    const k = Object.keys(coll)[0];
    return k ? (coll[k] || [])[0] : undefined;
  }
  return undefined;
}

function assertSnapshotShape(snap) {
  if (!snap || typeof snap !== 'object' || Array.isArray(snap)) {
    throw new Error('Resposta de /api/snapshot inesperada (não é um objeto BancoSnapshot).');
  }
  const bad = SNAPSHOT_SHAPE.filter(([k, ok]) => !ok(snap[k])).map(([k]) => k);
  if (bad.length) {
    throw new Error(`Resposta de /api/snapshot fora do contrato (campos inválidos: ${bad.join(', ')}).`);
  }
  const drifted = ROW_SHAPE
    .filter(([k, fields]) => {
      const row = firstRow(snap[k]);
      return row && fields.some((f) => !(f in row));
    })
    .map(([k]) => k);
  if (drifted.length) {
    throw new Error(`Resposta de /api/snapshot com linhas fora do contrato (${drifted.join(', ')}).`);
  }
}

async function fetchSnapshot(id) {
  const qs = new URLSearchParams({
    banco: id,
    currency: activeConv.currency,
    correction: activeConv.correction,
  });
  // Server-side flow filter: only sent when narrowing (a banco without a flow
  // dimension, or 'all', omits it → the BFF sums every flow, the historical default).
  if (activeFlow && activeFlow !== 'all') qs.set('flow', activeFlow);
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
  latestVersion: () => null, // no live Gold version signal yet (see isStale)
  latestAt: (id) => refreshOf(id),
  table: (id) => tableOf(id),

  // The active display conventions (currency/correction). The snapshot is fetched
  // and cached per-convention; producers that fetch their OWN convention-scoped
  // resources (e.g. the geo-yearly cube in producers.js, consumed by applyFilters)
  // read this so their value column matches the snapshot's exactly.
  conv: () => ({ ...activeConv }),

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
      // Keep the registry "última safra" LABEL but make its period live: overlay the
      // real latest year, and for monthly bancos (a "· Mnn" suffix) make the month
      // honest too — the real months elapsed in a still-partial latest year, or drop
      // the suffix once that year is complete. Without this the frozen literal would
      // claim e.g. "COMEX 2026 · M12" (December) for a year that only has 5 months.
      if (sm.yearEnd != null && typeof prov.lastCrop === 'string') {
        let lc = prov.lastCrop.replace(/\d{4}/, String(sm.yearEnd));
        if (/·\s*M\d{1,2}/.test(lc)) {
          lc =
            sm.latestYearComplete === false && sm.monthsInLatestYear != null
              ? lc.replace(/·\s*M\d{1,2}/, `· M${String(sm.monthsInLatestYear).padStart(2, '0')}`)
              : lc.replace(/\s*·\s*M\d{1,2}/, '');
        }
        prov.lastCrop = lc;
      }
    }
    return {
      table: (sm && sm.table) || tableOf(id),
      refresh: refreshOf(id),
      version: (sm && sm.version) || null,
      coverage: sm
        ? {
            yearStart: sm.yearStart,
            yearEnd: sm.yearEnd,
            totalRows: sm.totalRows,
            productsTotal: sm.productsTotal,
            ufsTotal: sm.ufsTotal,
          }
        : null,
      // Latest-year completeness signal (/api/source-meta, FINDING #3). Monthly
      // bancos (COMEX) publish the current year month-by-month, so yearEnd is
      // usually PARTIAL — a raw YoY against it reads a few months vs a full year
      // as a spurious crash. The Overview anchors its headline YoY on
      // latestCompleteYear when latestYearComplete === false. Annual bancos
      // (PEVS/PAM/COMTRADE) are always complete → null/true here, YoY unchanged.
      latest: sm
        ? {
            monthsInLatestYear: sm.monthsInLatestYear ?? null,
            // Default to complete when the field is absent (annual bancos, or an
            // older backend) so the YoY is only ever SUPPRESSED on a known-partial
            // year, never spuriously hidden.
            yearComplete: sm.latestYearComplete !== false,
            completeYear: sm.latestCompleteYear ?? null,
          }
        : null,
      source: b.source,
      scope: b.scope,
      domain: b.domain,
      cobertura: b.cobertura || null,
      maturity: b.maturity,
      // A forecast date only makes sense for a stage that has NO data yet
      // (e.g. planejado). Any data-bearing stage — incl. 'desenvolvimento',
      // which is now in production and consultable — must not surface one.
      maturityDate: (window.MATURITY?.[b.maturity]?.hasData)
        ? null
        : b.maturityDate || b.plannedRelease || null,
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
    // fetchSourceMeta shares the in-flight promise, so a concurrent load() (which
    // also kicks it) and this call resolve to a SINGLE network request (#8).
    return fetchSourceMeta(id);
  },

  // True once /api/source-meta has resolved for this banco — i.e. the live
  // maturity (the single source of truth, from BigQuery) is known. The DataGate
  // waits on this before deciding live-vs-placeholder, so a banco never flashes
  // the "Em breve" placeholder before its real maturity has loaded.
  hasMeta: (id) => !!sourceMeta[id],

  // Honest staleness: there is no live version/refresh polling yet, so we cannot
  // know a banco's cached snapshot went stale vs a newer Gold. Report never-stale
  // rather than drive the FreshnessBanner from a fabricated version. (To enable it
  // for real, poll /api/source-meta and compare its lastRefresh to the load time.)
  isStale: () => false,

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
    // Stamp this fetch; a later load()/reload() for the same key bumps it, marking
    // any in-flight older fetch's resolution stale so it cannot overwrite the newer.
    const myGen = (loadGen[key] || 0) + 1;
    loadGen[key] = myGen;
    notify();
    return fetchSnapshot(id)
      .then((data) => {
        if (loadGen[key] !== myGen) return store[key]; // superseded — keep the newer fetch's state
        store[key] = {
          status: 'ready',
          version: `${id}-live`,
          loadedAt: refreshOf(id) || 'agora',
          data,
          error: null,
        };
        notify();
        return store[key];
      })
      .catch((err) => {
        if (loadGen[key] !== myGen) return store[key]; // stale failure — don't clobber the newer fetch
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
  // currency/correction means a different deflated value column → re-fetch.
  //
  // The store caches per `${id}|${currency}|${correction}`, so the new convention
  // is a DIFFERENT cache key that nothing has loaded. A bare notify() would NOT
  // help: useBancoData only issues load() inside a useEffect keyed [bancoId], so a
  // re-render never re-runs the fetch — the gate would sit on the loading skeleton
  // forever (a deep-linked ?cur=USD/?corr=Nominal wedged every data view). So we
  // proactively re-run load() for every banco that was already loaded (or is
  // loading) under the PREVIOUS conventions, now under the new key, then notify.
  setConventions(conv) {
    if (!conv) return;
    const next = { currency: conv.currency || 'BRL', correction: conv.correction || 'IPCA' };
    if (next.currency === activeConv.currency && next.correction === activeConv.correction) return;
    // Bancos touched under any previous convention (cache keys are `id|cur|corr`).
    const loadedBancos = [...new Set(Object.keys(store).map((k) => k.split('|')[0]))];
    activeConv = next;
    notify();
    // Kick the snapshot fetch for the new convention's key so the gate resolves
    // instead of waiting on a [bancoId]-only effect that never re-fires.
    loadedBancos.forEach((id) => this.load(id));
  },

  // Flow bridge: the app calls this when the active flow (export/import) changes.
  // Flow is server-side (the trade snapshot is pre-aggregated over it), so a new
  // direction is a DIFFERENT cache key — re-fetch every already-loaded banco under
  // it, exactly like setConventions. 'all'/absent → sum every flow (the default).
  setFlow(flow) {
    const next = flow || 'all';
    if (next === activeFlow) return;
    const loadedBancos = [...new Set(Object.keys(store).map((k) => k.split('|')[0]))];
    activeFlow = next;
    notify();
    loadedBancos.forEach((id) => this.load(id));
  },

  // Re-run the active query (used by the freshness "Recarregar" + error retry).
  reload(id) {
    delete store[cacheKey(id)];
    return this.load(id);
  },
};
