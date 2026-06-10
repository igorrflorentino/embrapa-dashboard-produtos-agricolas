// enrichment.js — curation layer. MINIMAL for now: empty registries + a no-op
// enrichment object so ViewCuration renders without crashing. The full
// API-backed editor (worklist via /api/curation/worklist, writes via POST
// /api/curation/code-level, optimistic draft/commit) is wired in a follow-up
// (curation is read+write + has the data-blocked regime×flow market-nature axis).

window.ENRICH_LEVELS = window.ENRICH_LEVELS || [];
window.ENRICH_REGIMES = window.ENRICH_REGIMES || [];
window.ENRICH_FLOWS = window.ENRICH_FLOWS || [];
window.ENRICH_MARKETS = window.ENRICH_MARKETS || [];
window.ENRICH_GROUPS = window.ENRICH_GROUPS || [];

const noop = () => {};

window.enrichment = window.enrichment || {
  codes: () => [],
  regimes: () => [],
  flowTypes: () => [],
  pairMarket: () => null,
  setCode: noop,
  setPair: noop,
  apply: (cb) => {
    if (typeof cb === 'function') cb();
  },
  discard: noop,
  stats: () => ({
    codesTotal: 0,
    byLevel: { bruta: 0, processada: 0, misturado: 0 },
    unclassified: 0,
    flowsTotal: 0,
    flowsClassified: 0,
  }),
  pendingCount: () => 0,
  isCommitting: () => false,
  chapterOf: () => null,
  subscribe: () => noop,
};
