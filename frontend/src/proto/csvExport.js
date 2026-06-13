// csvExport.js — exports the data behind the ACTIVE view, honouring the
// active filters (period, basket, states, value range, quality flags).
// "Exactly what the view shows" — e.g. if the period filter excludes
// pre-2002, the file starts at 2002. Builds a CSV string and triggers a
// client-side download. (In the Cloud Run deploy, the same filtered slice
// is what's held in memory; this writes it out verbatim.)

(function () {
  // A view is exportable when its registry entry (views.js) declares
  // `exportable: true` — i.e. it has an applyFilters-backed tabular slice.
  // Selfdata preview views (fluxos, parceiros, sazonalidade), the cross-source
  // perspectives and the docs views omit the flag, so the export button is
  // hidden for them (see window.canExportView). Single source of truth: the
  // registry, not a parallel id list here.
  window.canExportView = (view) => !!(window.viewById && window.viewById(view)?.exportable);

  function toCSV(headers, rows) {
    const esc = (v) => {
      if (v == null) return '';
      const s = String(v);
      return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const head = headers.join(';');                 // pt-BR friendly delimiter
    const body = rows.map(r => r.map(esc).join(';')).join('\n');
    return '\uFEFF' + head + '\n' + body;           // BOM for Excel UTF-8
  }

  function download(filename, csv) {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Build the rows for the active view from the FILTERED datasets.
  function buildRows(ctx) {
    const { view, summary, conventions, database } = ctx;
    const conv = conventions || window.DEFAULT_CONVENTIONS;
    const f = window.applyFilters(summary || {}, database);
    const sym = (window.CURRENCY_FX[conv.currency] || { symbol: 'R$' }).symbol;
    const PRODS = f.products;
    const nameOf = (c) => (PRODS.find(p => p.code === c) || {}).name || c;

    // value/qty display transforms (same as the views use)
    const dispV = (vBi) => window.applyConv(vBi, conv);

    switch (view) {
      case 'value':
      case 'overview': {
        // annual aggregate series (value + qty per family)
        const headers = ['ano', `valor_${conv.currency}`, 'qtd_massa_t', 'qtd_volume_m3'];
        const rows = f.ts.map(d => [
          d.y,
          Math.round(dispV(d.v * 1e9)),
          Math.round(d.q_mass * 1e3),
          Math.round(d.q_vol * 1e6),
        ]);
        return { headers, rows, subject: 'serie_agregada' };
      }
      case 'product_profile':
      case 'product_compare': {
        // per-product annual series. productTS.q is in mil t for mass but mi m³ for
        // volume — scaling both by 1e3 (the old code) mixed t and mil m³ under one
        // unitless "quantidade" header. Scale per family to its base unit (mass→t,
        // volume→m³) and emit the unit explicitly so the column is unambiguous.
        const headers = ['ano', 'codigo', 'produto', `valor_${conv.currency}`, 'quantidade', 'unidade', 'familia'];
        const rows = [];
        Object.entries(f.productTS).forEach(([code, series]) => {
          const fam = (PRODS.find(p => p.code === code) || {}).family;
          const qMul = fam === 'volume' ? 1e6 : 1e3; // mil t→t, mi m³→m³
          const qUnit = fam === 'volume' ? 'm³' : 't';
          series.forEach(d => rows.push([
            d.y, code, nameOf(code),
            Math.round(dispV(d.v * 1e6)),
            Math.round(d.q * qMul),
            qUnit,
            fam,
          ]));
        });
        return { headers, rows, subject: 'series_por_produto' };
      }
      case 'geo': {
        const headers = ['uf', 'nome', 'regiao', `valor_${conv.currency}`, 'qtd_massa_t', 'qtd_volume_m3'];
        const rows = f.ufData.map(u => [
          u.uf, u.name, u.region,
          Math.round(dispV(u.value * 1e6)),
          Math.round(u.q_mass * 1e3),
          Math.round(u.q_vol * 1e6),
        ]);
        return { headers, rows, subject: 'distribuicao_geografica' };
      }
      case 'concentration': {
        const headers = ['uf', 'nome', 'regiao', `valor_${conv.currency}`];
        const rows = f.ufData.slice().sort((a, b) => b.value - a.value)
          .map(u => [u.uf, u.name, u.region, Math.round(dispV(u.value * 1e6))]);
        return { headers, rows, subject: 'concentracao' };
      }
      case 'quality': {
        const headers = ['flag', 'descricao', 'linhas', 'participacao'];
        const rows = f.qualityFlags.map(q => [q.id, q.label, q.count, (q.share * 100).toFixed(2).replace('.', ',') + '%']);
        return { headers, rows, subject: 'qualidade' };
      }
      default:
        return null;
    }
  }

  // Public entry — called by the "Exportar CSV" button.
  window.exportActiveTableCSV = function (ctx) {
    const banco = window.bancoById ? window.bancoById(ctx.database) : null;
    // Only live bancos hold real rows; soon bancos have nothing to export.
    if (!banco || banco.status !== 'live') {
      console.warn('[csv] banco not available for export:', ctx.database);
      return;
    }
    const built = buildRows(ctx);
    if (!built || !built.rows.length) {
      console.warn('[csv] nothing to export for view', ctx.view);
      return;
    }
    const period = (ctx.summary && ctx.summary.startDate)
      ? `${ctx.summary.startDate.slice(0,4)}-${(ctx.summary.endDate||'').slice(0,4)}`
      : 'completo';
    const fname = `${banco.short.replace(/\s+/g,'_').toLowerCase()}_${built.subject}_${period}.csv`;
    download(fname, toCSV(built.headers, built.rows));
  };
})();
