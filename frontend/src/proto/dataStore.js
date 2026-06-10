// dataStore.js — the pushdown query boundary that mirrors the Cloud Run
// deployment model:
//   • The Cloud Run service is STATELESS — no Gold is held in memory.
//   • Each UI interaction becomes a parameterized SQL query pushed down to
//     BigQuery, which returns a small pre-aggregated result (Serving Layer).
//   • flask-caching memoizes those results by params + Gold version; a poll
//     checks whether Gold changed upstream, invalidating the cache ("stale").
//
// All datasets are mock today. IBGE PEVS draws from the window.* globals
// (data.js); MDIC COMEX and UN Comtrade are LIVE on REPRESENTATIVE results
// (window.snapshotFor, previewData.js) generated from the explicit contract
// shape (02_SNAPSHOT_CONTRACTS.md); SEFAZ stays not-connected. When the real
// backend exists, replace
// `datasetFor()` with the pushdown query and `fetchGoldVersion()` with the
// real version poll. The view layer (window.applyFilters / preview adapters)
// does not change.

(function () {
  const store = {};          // bancoId -> { status, version, loadedAt, data }
  const subs  = new Set();
  const notify = () => subs.forEach(fn => { try { fn(); } catch (e) {} });

  // Simulated upstream Gold version per banco. Bumping `v` invalidates the
  // cached result (as if a new Medallion run published new data).
  // The PEVS publish timestamp is sourced from the banco registry
  // (bancos.js · prov.refresh) so it isn't duplicated as a literal here.
  const goldVersion = {
    ibge_pevs:   { v: 'pevs-2024.1', at: (window.bancoById && window.bancoById('ibge_pevs')?.prov?.refresh) || '28 mai 2026 · 04:30 BRT' },
    mdic_comex:  { v: 'comex-2024.12', at: (window.bancoById && window.bancoById('mdic_comex')?.prov?.refresh) || '29 mai 2026 · 05:10 BRT' },
    un_comtrade: { v: 'comtrade-2024.1', at: (window.bancoById && window.bancoById('un_comtrade')?.prov?.refresh) || '29 mai 2026 · 05:10 BRT' },
    ibge_pam:    { v: 'pam-2024.1', at: (window.bancoById && window.bancoById('ibge_pam')?.prov?.refresh) || '30 mai 2026 · 04:45 BRT' },
    sefaz_nf:    { v: 'nfe-preview', at: '—' },
  };

  // Gold table identifiers AS REPORTED BY THE BACKEND (the catalog the service
  // discovers at startup / version poll). This is the source of truth for the
  // table NAME shown in the UI — not a frontend literal — so a rename upstream
  // propagates everywhere via window.bancoTable(). In production, populate this
  // from the backend response; the registry `banco.table` is only a fallback.
  const goldTable = {
    ibge_pevs:   'gold_pevs_production',
    mdic_comex:  'gold_comex_flows',
    un_comtrade: 'gold_comtrade_flows',
    ibge_pam:    'gold_pam_production',
    sefaz_nf:    'gold_nfe_flows',
  };
  const tableOf = (id) => goldTable[id] || null;

  // The Serving-Layer result a banco exposes (the small pre-aggregated DataFrame
  // a pushdown query would return). IBGE PEVS references the existing
  // global tables (same object = same data). MDIC COMEX & UN Comtrade return a
  // SYNTHETIC, REPRESENTATIVE PEVS-shaped result (window.snapshotFor,
  // previewData.js) built from the explicit contract shape — they are LIVE, so their
  // perspectives render this data. SEFAZ (not connected) returns a result too,
  // but stays gated as a placeholder by its maturity in MainScreen.
  // When a banco gets real Gold, replace its branch with the pushdown query
  // (keep the returned shape — it IS the contract).
  function datasetFor(bancoId) {
    if (bancoId === 'ibge_pevs') {
      return {
        products:   window.PRODUCTS,
        productTS:  window.PRODUCT_TS,
        overviewTS: window.OVERVIEW_TS,
        ufData:     window.UF_DATA,
        quality:    window.QUALITY_FLAGS,
        // path-A extras so applyFilters can read EVERYTHING from the snapshot
        // (not from hardcoded globals) — keeps the seam banco-agnostic.
        qualityTs:  window.QUALITY_TS,
        topMunis:   window.TOP_MUNICIPIOS,
        regions:    window.REGIONS,
        qualityByProduct: window.QUALITY_BY_PRODUCT,
        qualityByUf:      window.QUALITY_BY_UF,
        table:      tableOf('ibge_pevs'),
      };
    }
    // Other bancos: representative snapshot from previewData.js (null if none).
    // Attach the backend-reported table name so it flows with the snapshot.
    const snap = (window.snapshotFor && window.snapshotFor(bancoId)) || null;
    if (snap) snap.table = tableOf(bancoId);
    return snap;
  }

  // Simulated bootstrap latency so the loading state is observable.
  const LOAD_MS = 650;

  window.dataStore = {
    status:    (id) => (store[id] && store[id].status) || 'idle',
    version:   (id) => (store[id] && store[id].version) || null,
    loadedAt:  (id) => (store[id] && store[id].loadedAt) || null,
    get:       (id) => (store[id] && store[id].data) || null,
    latestVersion: (id) => (goldVersion[id] && goldVersion[id].v) || null,
    latestAt:      (id) => (goldVersion[id] && goldVersion[id].at) || null,
    // Backend-reported Gold table name (source of truth for display).
    table:         (id) => tableOf(id),

    // Per-banco PROVENANCE METADATA as the backend would report it (single
    // payload): table, source, scope/granularity, coverage, refresh, counts,
    // implementation status + expected-completion. In production this is the
    // backend's response; here the authoritative live facts (table, refresh)
    // come from the catalogs above and the remaining descriptive fields fall
    // through to the registry as the stand-in. The UI reads this via
    // window.bancoMeta(id) so a change upstream propagates everywhere; swap
    // this body for the real backend call and nothing in the UI changes.
    meta: (id) => {
      const b = (window.bancoById && window.bancoById(id)) || {};
      return {
        table:      tableOf(id),
        refresh:    (goldVersion[id] && goldVersion[id].at) || (b.prov && b.prov.refresh) || null,
        version:    (goldVersion[id] && goldVersion[id].v) || null,
        source:     b.source,
        scope:      b.scope,
        domain:     b.domain,
        cobertura:  b.cobertura || null,
        maturity:   b.maturity,
        // A conclusion/expected date only applies to NON-estavel bancos; an
        // estavel (production) banco never shows one (ignore any legacy plannedRelease).
        maturityDate: (b.maturity === 'estavel') ? null : (b.maturityDate || b.plannedRelease || null),
        prov:       b.prov || null,
      };
    },

    // Is the cached result behind the upstream Gold version?
    isStale: (id) =>
      !!(store[id] && store[id].status === 'ready' &&
         goldVersion[id] && store[id].version !== goldVersion[id].v),

    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },

    // Run (or re-run) a banco's pushdown query and cache the result.
    load(id) {
      const fresh = store[id] && store[id].status === 'ready' && !this.isStale(id);
      if (fresh) return Promise.resolve(store[id]);
      store[id] = { status: 'loading', version: null, loadedAt: null, data: null, error: null };
      notify();
      return new Promise((resolve) => {
        setTimeout(() => {
          try {
            // Simulated transient failure hook (see failNext below). In prod
            // this is where a query/timeout/auth error would be caught.
            if (this._failNext[id]) {
              this._failNext[id] = false;
              throw new Error('Falha ao consultar a tabela Gold no BigQuery (timeout).');
            }
            store[id] = {
              status:   'ready',
              version:  (goldVersion[id] && goldVersion[id].v) || (id + '-preview'),
              loadedAt: (goldVersion[id] && goldVersion[id].at) || 'agora',
              data:     datasetFor(id),
              error:    null,
            };
          } catch (err) {
            store[id] = { status: 'error', version: null, loadedAt: null, data: null,
                          error: (err && err.message) || 'Erro desconhecido ao carregar dados.' };
          }
          notify();
          resolve(store[id]);
        }, LOAD_MS);
      });
    },

    error: (id) => (store[id] && store[id].error) || null,

    // DEMO: arm a one-shot load failure for a banco (to exercise the error UI).
    _failNext: {},
    simulateError(id) { this._failNext[id] = true; notify(); },

    // DEMO: simulate Gold being updated upstream (flips loaded snapshot to stale).
    bumpGold(id) {
      const cur = goldVersion[id] || { v: id + '-1' };
      const m = cur.v.match(/(\d+)$/);
      const next = m ? cur.v.replace(/\d+$/, String(parseInt(m[1], 10) + 1)) : cur.v + '.2';
      const now = new Date();
      goldVersion[id] = {
        v: next,
        at: now.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }) + ' · ' +
            now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) + ' BRT',
      };
      notify();
    },
  };
})();
