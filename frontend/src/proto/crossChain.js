// crossChain.js — EXTENDED cross-source contracts. SHAPES defined once in
// contracts.js (@typedef ChainBalance / HarvestShipmentLag). These go beyond
// the annual scalar series of crossSource.js, in the two ways flagged as
// "extend the contract, not the layout":
//
//   chainBalance(productCode, year)  → a RECONCILED supply balance:
//       produced = internal + exported + domestic   (mass conserved),
//       plus the export's slice of the world market (value basis).
//       Shape feeds the existing <SankeyChart> (nodes/links) unchanged.
//
//   harvestShipmentLag(productCode)  → MONTHLY profiles + lead-lag:
//       harvest (modeled monthly from annual PEVS) vs shipments (MDIC
//       monthly), with the cross-correlation over ±6 months.
//
// Both are PREVIEW until the trade/internal bancos go live. Real wiring:
// swap the synthetic bodies for queries returning the SAME shapes.
//
// NOTE on resolution: PEVS production is published ANNUALLY, so the
// monthly harvest curve here is a MODEL (a seasonal distribution of the
// annual total), not measured monthly data — the view labels it as such.

(function () {
  // Shared synth helpers (previewFor, seeded, productScale) live in
  // synthUtils.js; used here via window.* — no local copies.

  // ── (5) Chain balance — reconciled mass split + world-market context ──
  window.chainBalance = function (productCode, year) {
    year = year || 2024;
    const scale = window.productScale(productCode);
    const ovTs = window.OVERVIEW_TS || [];
    const row = ovTs.find(d => d.y === year) || ovTs[ovTs.length - 1];
    const produced = (row?.q_mass || 2884) * scale;            // mil t (real PEVS side)

    const rnd = window.seeded('chain:' + (productCode || 'all') + ':' + year);
    let expFrac = 0.34 + rnd() * 0.12;     // exported share of production
    let intFrac = 0.26 + rnd() * 0.12;     // internally traded share
    if (expFrac + intFrac > 0.86) { const k = 0.86 / (expFrac + intFrac); expFrac *= k; intFrac *= k; }
    const exported = produced * expFrac;
    const internal = produced * intFrac;
    const domestic = Math.max(0, produced - exported - internal);  // consumption / stock residual

    // Export's slice of the world market (value basis, via marketShare).
    const ms = window.marketShare ? window.marketShare(productCode) : null;
    const msRow = ms ? (ms.series.find(d => d.y === year) || ms.series[ms.series.length - 1]) : null;
    const worldShare = msRow?.share || 0;
    const worldTotal = msRow?.world || 0;
    const exportUsd = msRow?.br || 0;

    // Supply balance as a 2-column flow (Production → destinations) for SankeyChart.
    const nodes = [
      { id: 'prod', label: 'Produção',          side: 'origin', value: produced },
      { id: 'exp',  label: 'Exportação',        side: 'dest',   value: exported },
      { id: 'int',  label: 'Comércio interno',  side: 'dest',   value: internal },
      { id: 'dom',  label: 'Consumo / estoque', side: 'dest',   value: domestic },
    ];
    const links = [
      { source: 'prod', target: 'exp', value: exported },
      { source: 'prod', target: 'int', value: internal },
      { source: 'prod', target: 'dom', value: domestic },
    ];

    return {
      preview: window.previewFor('ibge_pevs','sefaz_nf','mdic_comex','un_comtrade'), unit: 'mil t', year,
      produced, exported, internal, domestic,
      expFrac: exported / (produced || 1), intFrac: internal / (produced || 1), domFrac: domestic / (produced || 1),
      worldShare, worldTotal, exportUsd,
      sankey: { nodes, links },
    };
  };

  // ── (6) Harvest → shipment lead-lag ───────────────────────────────────
  window.harvestShipmentLag = function (productCode) {
    const rnd = window.seeded('lag:' + (productCode || 'all'));
    const peak = Math.floor(rnd() * 12);        // harvest peak month (0–11)
    const lagTrue = 1 + Math.floor(rnd() * 4);  // baked-in shipment lag (1–4 months)

    const prod = [], ship = [];
    const circDist = (m, c) => Math.min((m - c + 12) % 12, (c - m + 12) % 12);
    const shipPeak = (peak + lagTrue) % 12;
    for (let m = 0; m < 12; m++) {
      prod.push(1 + Math.exp(-Math.pow(circDist(m, peak) / 2.2, 2)) * 2.6 + (rnd() - 0.5) * 0.5);
      ship.push(1 + Math.exp(-Math.pow(circDist(m, shipPeak) / 2.7, 2)) * 2.2 + (rnd() - 0.5) * 0.5);
    }
    const norm = (a) => { const mx = Math.max(...a); return a.map(v => (v / mx) * 100); };

    const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length;
    const mp = mean(prod), msh = mean(ship);
    // corr at lag L = corr(production[m], shipments[m+L]); +L ⇒ shipments lag harvest by L.
    const corrAt = (lag) => {
      let num = 0, dp = 0, ds = 0;
      for (let m = 0; m < 12; m++) {
        const si = (m + lag + 12) % 12;
        const xp = prod[m] - mp, xs = ship[si] - msh;
        num += xp * xs; dp += xp * xp; ds += xs * xs;
      }
      return (dp && ds) ? num / Math.sqrt(dp * ds) : 0;
    };
    const lagProfile = [];
    for (let l = -6; l <= 6; l++) lagProfile.push({ lag: l, corr: corrAt(l) });
    const best = lagProfile.reduce((b, d) => d.corr > b.corr ? d : b, lagProfile[0]);

    return {
      preview: window.previewFor('ibge_pevs','mdic_comex'),
      months: window.MONTH_LABELS || ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'],
      production: norm(prod), shipments: norm(ship),
      peakHarvest: peak, peakShip: shipPeak,
      lagMonths: best.lag, corrAtLag: best.corr, lagProfile,
    };
  };
})();
