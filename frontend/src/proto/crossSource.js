// crossSource.js — the DATA CONTRACT behind the "Cruzamento entre fontes"
// perspective. It exposes one comparable ANNUAL time series per
// (banco, metric) pair, so series from DIFFERENT bancos can be charted on
// the same time axis (e.g. IBGE annual production × MDIC annual exports).
//
// ─────────────────────────────────────────────────────────────────────
// WHY THIS FILE EXISTS (handoff note for the backend team)
//   The cross-source VIEW (ViewCrossSource.jsx) and CHARTS (Charts.cross.jsx)
//   never touch raw data — they only consume `window.crossSeries(...)`.
//   To wire a real banco you replace ONE builder body below and keep the
//   returned shape identical. No view/chart/router code changes.
//
// CONTRACT
//   window.crossSeries(bancoId, metricId, { y0, y1 }) → SeriesResult | null
//
//   SHAPE (SeriesResult) is defined once in contracts.js (@typedef
//   SeriesResult) — the single source of truth. Two series share a Y axis /
//   can form a ratio IFF their `unit` strings are identical (see
//   ViewCrossSource); `family` groups them more loosely for labelling.
//
//   When the banco goes live: in SERIES_BUILDERS, swap the synthetic body
//   for `dataStore.get(bancoId)` reads (or a real query) that emit the same
//   { y, v } array, and set preview:false (or derive it from banco.status).
// ─────────────────────────────────────────────────────────────────────

(function () {
  // Deterministic PRNG (window.seeded) and macro-shock curve (window.macroShock)
  // live in synthUtils.js — used here via window.* so the synthetic series stay
  // in lockstep with the other cross-source / preview builders.

  // Build a smooth growing synthetic annual series from v0→vT across the
  // metric's coverage, with mild seeded noise + macro shocks. Returns the
  // FULL native-coverage array; crossSeries() trims it to the request window.
  function synthSeries(seed, [start, end], v0, vT) {
    const rnd = window.seeded(seed);
    const n = end - start;
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const y = start + i;
      const t = i / (n || 1);
      // gentle S-curve so growth accelerates then eases
      const ease = t * t * (3 - 2 * t);
      const base = v0 + (vT - v0) * ease;
      const noise = 1 + (rnd() - 0.5) * 0.07;
      pts.push({ y, v: base * noise * window.macroShock(y) });
    }
    return pts;
  }

  // ── Real (live) adapter: IBGE PEVS — derive annual series from the
  //    in-memory Gold mock (window.OVERVIEW_TS). These are REAL numbers in
  //    the mock's native magnitudes; the display units below match them.
  function pevs(metricId) {
    const ts = window.OVERVIEW_TS || [];
    if (metricId === 'prod_value')  return ts.map(d => ({ y: d.y, v: d.v }));      // R$ bi
    if (metricId === 'prod_mass')   return ts.map(d => ({ y: d.y, v: d.q_mass }));  // mil t
    if (metricId === 'prod_volume') return ts.map(d => ({ y: d.y, v: d.q_vol }));   // mi m³
    return [];
  }

  // ── Display unit per (banco, metric). Conceptual units live in bancos.js
  //    (metric.unit); these add the working magnitude used on the axes.
  const DISPLAY_UNIT = {
    'ibge_pevs:prod_value':  'R$ bi',
    'ibge_pevs:prod_mass':   'mil t',
    'ibge_pevs:prod_volume': 'mi m³',
    'mdic_comex:exp_value':  'US$ bi',
    'mdic_comex:imp_value':  'US$ bi',
    'mdic_comex:exp_weight': 'mil t',
    'mdic_comex:exp_price':  'US$/kg',
    'un_comtrade:exp_value': 'US$ bi',
    'un_comtrade:imp_value': 'US$ bi',
    'un_comtrade:world_exp': 'US$ bi',
    'sefaz_nf:internal_value':  'R$ bi',
    'sefaz_nf:internal_weight': 'mil t',
    'sefaz_nf:icms_total':      'R$ bi',
    'ibge_pam:prod_value':      'R$ bi',
    'ibge_pam:prod_quantity':   'mi t',
    'ibge_pam:area_harvested':  'mi ha',
    'ibge_pam:yield':           'kg/ha',
  };

  // ── SERIES BUILDERS — the ONE place per (banco, metric) where data is
  //    produced. Live banco → real reads. Soon bancos → synthetic preview.
  //    Replace a synthetic body with a real query and the rest is unchanged.
  //    Demo magnitude ranges [v0, vT] live in demoFixture.js (window.DEMO_PARAMS
  //    .crossMagnitudes); edit that file to demo a different chain. The seed
  //    strings stay fixed so the synthetic output is deterministic across runs.
  const MAG = (window.DEMO_PARAMS && window.DEMO_PARAMS.crossMagnitudes) || {};
  const magSeries = (seed, key, cov) => {
    const [v0, vT] = MAG[key] || [1, 2];
    return synthSeries(seed, cov, v0, vT);
  };
  const SERIES_BUILDERS = {
    // ---- IBGE PEVS (live) ----
    'ibge_pevs:prod_value':  () => pevs('prod_value'),
    'ibge_pevs:prod_mass':   () => pevs('prod_mass'),
    'ibge_pevs:prod_volume': () => pevs('prod_volume'),

    // ---- MDIC COMEX (representative demo magnitudes — castanha/nut chain) ----
    'mdic_comex:exp_value':  (cov) => magSeries('mdic:exp_value', 'mdic_comex:exp_value', cov),
    'mdic_comex:imp_value':  (cov) => magSeries('mdic:imp_value', 'mdic_comex:imp_value', cov),
    'mdic_comex:exp_weight': (cov) => magSeries('mdic:exp_weight', 'mdic_comex:exp_weight', cov),
    // price = value(US$) ÷ weight, kept consistent with the two series above.
    'mdic_comex:exp_price':  (cov) => {
      const val = magSeries('mdic:exp_value', 'mdic_comex:exp_value', cov);   // US$ bi
      const wt  = magSeries('mdic:exp_weight', 'mdic_comex:exp_weight', cov); // mil t
      return val.map((d, i) => ({ y: d.y, v: (d.v * 1e9) / ((wt[i].v || 1) * 1e6) })); // US$/kg
    },

    // ---- UN COMTRADE (representative demo magnitudes — HS 0801) ----
    'un_comtrade:exp_value': (cov) => magSeries('comtrade:exp_value', 'un_comtrade:exp_value', cov),
    'un_comtrade:imp_value': (cov) => magSeries('comtrade:imp_value', 'un_comtrade:imp_value', cov),
    'un_comtrade:world_exp': (cov) => magSeries('comtrade:world_exp', 'un_comtrade:world_exp', cov),

    // ---- SEFAZ NFe (preview) ----
    'sefaz_nf:internal_value':  (cov) => magSeries('sefaz:internal_value', 'sefaz_nf:internal_value', cov),
    'sefaz_nf:internal_weight': (cov) => magSeries('sefaz:internal_weight', 'sefaz_nf:internal_weight', cov),
    'sefaz_nf:icms_total':      (cov) => magSeries('sefaz:icms_total', 'sefaz_nf:icms_total', cov),

    // ---- IBGE PAM (representative demo magnitudes — lavouras) ----
    'ibge_pam:prod_value':      (cov) => magSeries('pam:prod_value', 'ibge_pam:prod_value', cov),
    'ibge_pam:prod_quantity':   (cov) => magSeries('pam:prod_quantity', 'ibge_pam:prod_quantity', cov),
    'ibge_pam:area_harvested':  (cov) => magSeries('pam:area_harvested', 'ibge_pam:area_harvested', cov),
    'ibge_pam:yield':           (cov) => magSeries('pam:yield', 'ibge_pam:yield', cov),
  };

  // ── Public: one comparable annual series ─────────────────────────────
  window.crossSeries = function (bancoId, metricId, win) {
    const bancoMeta  = window.bancoById ? window.bancoById(bancoId) : null;
    const metricMeta = window.metricById ? window.metricById(bancoId, metricId) : null;
    if (!bancoMeta || !metricMeta) return null;

    const key = bancoId + ':' + metricId;
    const cov = metricMeta.years || [1986, 2024];
    const builder = SERIES_BUILDERS[key];
    const raw = builder ? builder(cov) : [];

    const y0 = (win && win.y0) || cov[0];
    const y1 = (win && win.y1) || cov[1];
    const points = raw.filter(d => d.y >= y0 && d.y <= y1);

    return {
      banco: bancoId,
      metric: metricId,
      bancoMeta, metricMeta,
      key,
      label: metricMeta.label,
      unit: DISPLAY_UNIT[key] || metricMeta.unit || '',
      family: metricMeta.family,
      preview: bancoMeta.status !== 'live',
      coverage: cov,
      points,
    };
  };

  // ── Public: the common comparable window across a set of refs ─────────
  //   refs: [{ banco, metric }]. Returns { y0, y1, union:[a,b] }.
  //   y0..y1 is the INTERSECTION (where every series has data); union is the
  //   widest span any series covers (used as the slider bounds).
  window.crossCommonWindow = function (refs) {
    const covs = (refs || [])
      .map(r => window.metricById(r.banco, r.metric))
      .filter(Boolean)
      .map(m => m.years || [1986, 2024]);
    if (!covs.length) return { y0: 1997, y1: 2024, union: [1986, 2024] };
    const y0 = Math.max(...covs.map(c => c[0]));   // latest start
    const y1 = Math.min(...covs.map(c => c[1]));   // earliest end
    const union = [Math.min(...covs.map(c => c[0])), Math.max(...covs.map(c => c[1]))];
    // If coverages don't overlap, fall back to the union so the chart still draws.
    return y0 <= y1 ? { y0, y1, union } : { y0: union[0], y1: union[1], union };
  };

  // Coverage lint: every metric of every visible banco needs a series builder
  // (otherwise it appears in the picker but plots an empty line).
  if (window.auditBancoCoverage) {
    window.auditBancoCoverage('cruzamento · series builders (crossSource.js)',
      (b) => (b.metrics || []).every(m => SERIES_BUILDERS[b.id + ':' + m.id]));
  }
})();
