// synthUtils.js — shared helpers for the synthetic/preview data layer.
//
// These were copy-pasted, byte-for-byte, across crossAnalytics.js,
// crossSource.js, crossChain.js, previewData.js and enrichment.js. Centralized
// here so the deterministic seed sequence, macro-shock curve and preview/scale
// rules have a SINGLE definition — change once, every synthetic series follows.
//
// Pure + dependency-light: only `previewFor`/`productScale` touch window.* (the
// banco registry / PEVS globals), and only at call time. Load this BEFORE any
// file that builds synthetic data.

(function () {
  // Deterministic pseudo-random from a string seed (FNV-1a hash → mix), stable
  // across reloads so synthetic numbers never jump between loads. Returns a
  // function producing successive floats in [0, 1).
  function seeded(seed) {
    let h = 2166136261;
    for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
    return () => { h += 0x6D2B79F5; let t = Math.imul(h ^ (h >>> 15), 1 | h); t ^= t + Math.imul(t ^ (t >>> 7), 61 | t); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // Macro shocks shared by every synthetic series so the curves read as real:
  // 2009 global financial crisis dip, 2015–16 recession, 2020 COVID dip.
  // Returns a multiplier (1 = no shock) for a given year.
  function macroShock(year) {
    if (year === 2009) return 0.90;
    if (year === 2015 || year === 2016) return 0.94;
    if (year === 2020) return 0.92;
    return 1;
  }

  // Preview flag for a cross-banco analytic: true iff ANY source banco isn't
  // live yet (so the view shows the synthetic-demo banner).
  function previewFor(...ids) {
    return ids.some(id => ((window.bancoById && window.bancoById(id)) || {}).status !== 'live');
  }

  // Product weight: a single commodity's share of the latest-year basket value
  // (window.PRODUCT_TS), used to scale aggregates when one product is selected.
  // null/absent code = whole basket → scale 1. Floored at 0.02 so a tiny
  // commodity still draws a visible series.
  function productScale(code) {
    if (!code) return 1;
    const series = (window.PRODUCT_TS || {})[code];
    if (!series) return 1;
    const last = series[series.length - 1]?.v || 0;
    const total = Object.values(window.PRODUCT_TS || {})
      .reduce((s, ser) => s + (ser[ser.length - 1]?.v || 0), 0) || 1;
    return Math.max(0.02, last / total);
  }

  Object.assign(window, { seeded, macroShock, previewFor, productScale });
})();
