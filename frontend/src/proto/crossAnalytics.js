// crossAnalytics.js — DATA CONTRACTS for the four analytical multi-source
// perspectives (export coefficient, world market share, farm-gate vs FOB
// price, trade mirror). SHAPES defined once in contracts.js (@typedef
// ExportCoefficient / MarketShare / PriceSpread / TradeMirror). Same handoff
// rule as crossSource.js: views read ONLY through these window functions; to
// go live the backend swaps each body for a real query and keeps the shape.
//
// The preview flag is now DERIVED per call from the source bancos' live
// status (see previewFor): an analytic shows the demo banner only while one of
// its sources isn't live. With MDIC COMEX (estavel) and UN Comtrade
// (beta) live, their analytics render on the representative snapshots
// without the banner; analytics that still touch SEFAZ stay preview until it
// connects. The IBGE side (production) is real.
//
// The product join (PEVS extractive code ↔ NCM/HS in trade bancos) is a
// crosswalk the backend will own; here `productCode` just reseeds/scales
// the synthetic series so the UI exercises the parameter end to end.

(function () {
  // Shared synth helpers (seeded, previewFor, productScale) live in
  // synthUtils.js; use them via window.* — no local copies.

  // Bigger agro/extractive states lean more export-oriented.
  const EXPORT_LEAN = { PA: 0.62, MT: 0.66, PR: 0.58, RS: 0.54, AM: 0.34, AC: 0.30, RO: 0.28, BA: 0.36, SC: 0.44, GO: 0.40, MA: 0.32, SP: 0.5 };

  // ── (1) Export coefficient — production (PEVS) × export (MDIC) by UF ──
  //   SHAPE: contracts.js @typedef ExportCoefficient.
  window.exportCoefficient = function (productCode) {
    const scale = window.productScale(productCode);
    const rnd = window.seeded('coef:' + (productCode || 'all'));
    const byUf = (window.UF_DATA || []).map(u => {
      const production = u.q_mass * scale;                 // mil t (real PEVS side)
      const lean = (EXPORT_LEAN[u.uf] ?? 0.22) + (rnd() - 0.5) * 0.12;
      const coef = Math.max(0.03, Math.min(0.92, lean));
      return {
        uf: u.uf, name: u.name, region: u.region, col: u.col, row: u.row,
        production,
        exportV: production * coef,
        coefPct: coef * 100,
      };
    });
    const production = byUf.reduce((s, d) => s + d.production, 0);
    const exportV = byUf.reduce((s, d) => s + d.exportV, 0);
    const coefNat = production ? exportV / production : 0;
    // National coefficient drifting up over the MDIC coverage (1997→2024).
    const ts = window.seeded('coefts:' + (productCode || 'all'));
    const timeseries = [];
    for (let y = 1997; y <= 2024; y++) {
      const t = (y - 1997) / 27;
      const v = (coefNat * (0.72 + t * 0.4)) * (1 + (ts() - 0.5) * 0.05);
      timeseries.push({ y, v: Math.min(0.95, v) * 100 });
    }
    return { preview: window.previewFor('ibge_pevs','mdic_comex'), unit: 'mil t', byUf, national: { production, exportV, coefPct: coefNat * 100 }, timeseries };
  };

  // ── (2) World market share — BR exports ÷ world exports (Comtrade) ────
  //   SHAPE: contracts.js @typedef MarketShare.
  window.marketShare = function (productCode) {
    const scale = window.productScale(productCode);
    const br = window.crossSeries('mdic_comex', 'exp_value', { y0: 1997, y1: 2024 });
    const world = window.crossSeries('un_comtrade', 'world_exp', { y0: 1997, y1: 2024 });
    const series = br.points.map((d, i) => {
      const brV = d.v * scale;
      const worldV = (world.points[i]?.v || 1) * (0.6 + 0.4 * scale); // world also narrows for a single commodity
      return { y: d.y, br: brV, world: worldV, share: (brV / worldV) * 100 };
    });
    const byProduct = (window.PRODUCTS || []).map(p => {
      const r = window.seeded('share:' + p.code)();
      return { code: p.code, name: p.name, share: 2 + r * 26 };
    }).sort((a, b) => b.share - a.share);
    return { preview: window.previewFor('mdic_comex','un_comtrade'), unit: 'US$ bi', series, byProduct };
  };

  // ── (3) Farm-gate vs FOB price — PEVS implied price × MDIC export price ─
  //   SHAPE: contracts.js @typedef PriceSpread.
  window.priceSpread = function (productCode) {
    const fobS = window.crossSeries('mdic_comex', 'exp_price', { y0: 1997, y1: 2024 });
    const rnd = window.seeded('gate:' + (productCode || 'all'));
    const series = fobS.points.map((d, i) => {
      const t = i / (fobS.points.length - 1 || 1);
      // gate captures a shrinking fraction of FOB over time (widening spread)
      const frac = (0.50 - t * 0.16) * (1 + (rnd() - 0.5) * 0.06);
      const fob = d.v;
      const gate = fob * frac;
      return { y: d.y, gate, fob, spread: fob - gate, markup: gate ? fob / gate : 0 };
    });
    return { preview: window.previewFor('ibge_pevs','mdic_comex'), unit: 'US$/kg', series };
  };

  // ── (4) Trade mirror — same exports reported by different sources ─────
  //   SHAPE: contracts.js @typedef TradeMirror.
  window.tradeMirror = function (productCode) {
    const scale = window.productScale(productCode);
    const base = window.crossSeries('mdic_comex', 'exp_value', { y0: 1997, y1: 2024 });
    const rc = window.seeded('mirror_c:' + (productCode || 'all'));
    const rp = window.seeded('mirror_p:' + (productCode || 'all'));
    const series = base.points.map(d => {
      const mdic = d.v * scale;
      const comtrade = mdic * (0.965 + (rc() - 0.5) * 0.05);   // slight under-report
      const partners = mdic * (1.045 + (rp() - 0.5) * 0.06);   // partners over-report
      return { y: d.y, mdic, comtrade, partners };
    });
    const discrepancy = series.map(d => {
      const vals = [d.mdic, d.comtrade, d.partners];
      const max = Math.max(...vals), min = Math.min(...vals);
      const mean = (d.mdic + d.comtrade + d.partners) / 3 || 1;
      return { y: d.y, v: ((max - min) / mean) * 100 };
    });
    return { preview: window.previewFor('mdic_comex','un_comtrade'), unit: 'US$ bi', series, discrepancy };
  };
})();
