// ViewProductCompare — compare 2–4 commodities side by side.
// Normalized series (base 100), accumulated change, CAGR, and pairwise
// correlation. Honours active filters (selectable products limited to
// the basket) and conventions (currency for the absolute table column).

const { useState: usePCState } = React;

function ViewProductCompare({ summary, conventions, database }) {
  const conv     = conventions || window.DEFAULT_CONVENTIONS;
  const cvf      = window.convFactor(conv);   // base-aware value factor

  const filtered  = window.applyFilters(summary || {}, database);
  const available = filtered.selectedProducts.filter(c => filtered.allProductTS[c]);

  const COLORS = ['var(--viz-1)', 'var(--viz-3)', 'var(--viz-5)', 'var(--viz-7)'];
  const MAX = 4;

  // Default: top 3 by latest value
  const defaultSel = available
    .map(c => ({ c, v: filtered.allProductTS[c].slice(-1)[0]?.v || 0 }))
    .sort((a, b) => b.v - a.v)
    .slice(0, 3)
    .map(x => x.c);
  const [sel, setSel] = usePCState(defaultSel);

  // Keep selection valid against the current basket
  const active = sel.filter(c => available.includes(c)).slice(0, MAX);
  const activeSel = active.length ? active : defaultSel;

  const toggle = (c) => {
    setSel(prev => {
      const cur = prev.filter(x => available.includes(x));
      if (cur.includes(c)) return cur.filter(x => x !== c);
      if (cur.length >= MAX) return cur; // cap at 4
      return [...cur, c];
    });
  };

  const yearStart = filtered.yearStart, yearEnd = filtered.yearEnd;

  // Build per-product windows + metrics
  const items = activeSel.map((code, i) => {
    const prod = filtered.products.find(p => p.code === code);
    const win = filtered.allProductTS[code].filter(d => d.y >= yearStart && d.y <= yearEnd);
    const v0 = win[0]?.v || 0, vT = win[win.length - 1]?.v || 0;
    return {
      code, prod, win,
      color: COLORS[i % COLORS.length],
      v0, vT,
      cagr: window.cagrPct(v0, vT, win.length - 1),
      accum: window.accumPct(v0, vT),
      absT: vT * 1e6 * cvf,
    };
  });

  // Normalized series (base 100 at yearStart)
  const normSeries = items.map(it => ({
    name: it.prod.name,
    color: it.color,
    data: it.win.map(d => ({ y: d.y, v: it.v0 ? (d.v / it.v0) * 100 : 0 })),
  }));

  // Pairwise Pearson correlation on YoY growth, aligned BY YEAR (not array index):
  // a product with an internal year gap would otherwise correlate mismatched years.
  const corrMatrix = items.map(a => items.map(b => window.pearsonByYear(a.win, b.win)));
  const corrColor = window.corrColor;

  return (
    <>
      {/* Selector */}
      <div className="pp-selector">
        <span className="pp-selector-label">Comparar commodities <small className="pc-cap">(até {MAX})</small></span>
        <div className="pp-chips">
          {available.map(c => {
            const p = filtered.products.find(x => x.code === c);
            const on = activeSel.includes(c);
            const idx = activeSel.indexOf(c);
            const atCap = !on && activeSel.length >= MAX;
            return (
              <button key={c}
                      className={'pp-chip ' + (on ? 'on' : '') + (atCap ? ' disabled' : '')}
                      onClick={() => !atCap && toggle(c)}
                      style={on ? { background: COLORS[idx % COLORS.length], borderColor: COLORS[idx % COLORS.length], color: '#fff' } : null}
                      title={atCap ? `Máximo de ${MAX} commodities` : p.name}>
                <span className={'pp-chip-fam ' + p.family}></span>
                {p.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Normalized series */}
      <div className="card">
        <window.SectionHeader
          overline={`Séries normalizadas · base 100 em ${yearStart}`}
          title="Evolução relativa do valor"
          action={<span className="caption">{items.length} commodities</span>}
        />
        <window.MultiLineChart series={normSeries} label={`índice (${yearStart}=100)`} valueKey="v" height={300} />
        <div className="pc-legend">
          {items.map(it => (
            <span key={it.code} className="pc-legend-item">
              <span className="pc-legend-dot" style={{ background: it.color }}></span>
              {it.prod.name}
            </span>
          ))}
        </div>
      </div>

      {/* Metrics table */}
      <div className="card">
        <window.SectionHeader
          overline={`Métricas comparativas · ${yearStart}–${yearEnd}`}
          title="Crescimento e magnitude"
        />
        <div className="pc-table-wrap">
          <table className="pc-table">
            <thead>
              <tr>
                <th>Commodity</th>
                <th className="num">Valor {yearEnd}</th>
                <th className="num">Variação acumulada</th>
                <th className="num">CAGR (a.a.)</th>
                <th className="num">Família</th>
              </tr>
            </thead>
            <tbody>
              {items.map(it => (
                <tr key={it.code}>
                  <td>
                    <span className="pc-row-dot" style={{ background: it.color }}></span>
                    {it.prod.name}
                  </td>
                  <td className="num tnum">{window.formatValue(it.vT * 1e6, conv)}</td>
                  <td className="num tnum" style={{ color: it.accum >= 0 ? 'var(--ok)' : 'var(--err)' }}>
                    {window.fmtSigned(it.accum, 0)}
                  </td>
                  <td className="num tnum" style={{ color: it.cagr >= 0 ? 'var(--ok)' : 'var(--err)' }}>
                    {window.fmtSigned(it.cagr, 1)}
                  </td>
                  <td className="num">{window.UNIT_FAMILIES[it.prod.family].label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Correlation matrix */}
      <div className="card">
        <window.SectionHeader
          overline="Correlação cruzada · variação interanual"
          title="Quão sincronizadas são as trajetórias"
          action={<span className="caption">Pearson · −1 a +1</span>}
        />
        {items.length < 2 ? (
          <p className="caption" style={{ padding: '20px 4px', textAlign: 'center' }}>
            Selecione ao menos 2 commodities para calcular correlação.
          </p>
        ) : (
          <div className="pc-corr-wrap">
            <table className="pc-corr">
              <thead>
                <tr>
                  <th></th>
                  {items.map(it => (
                    <th key={it.code} title={it.prod.name}>
                      <span className="pc-corr-dot" style={{ background: it.color }}></span>
                      {it.prod.code}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((rowIt, i) => (
                  <tr key={rowIt.code}>
                    <th title={rowIt.prod.name}>
                      <span className="pc-corr-dot" style={{ background: rowIt.color }}></span>
                      {rowIt.prod.name}
                    </th>
                    {items.map((colIt, j) => {
                      const r = corrMatrix[i][j];
                      return (
                        <td key={colIt.code}
                            className="tnum"
                            style={{ background: i === j ? 'var(--bg-surface-2)' : corrColor(r), color: Math.abs(r) > 0.6 ? '#fff' : 'var(--fg-1)' }}>
                          {i === j ? '—' : r.toFixed(2).replace('.', ',')}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption pc-corr-note">
              Verde: trajetórias que sobem e descem juntas. Vermelho: movimentos opostos.
            </p>
          </div>
        )}
      </div>
    </>
  );
}

window.ViewProductCompare = ViewProductCompare;
