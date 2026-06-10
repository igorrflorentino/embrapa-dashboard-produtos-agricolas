// ViewQuality — data-quality diagnostics across the banco.
// Honours active filters: selected flags, selected products (per-product
// breakdown), selected UFs (geographic quality map), and year window.

// Maps each data_quality_flag id to its key in window.QUALITY_TS.
// Most are just the lowercased id, but BOUNDARY_HISTORIC is stored as
// `boundary` in the time series — without this map that band renders
// flat-zero and the temporal stack never reaches 100%.
const QTS_KEY = {
  OK: 'ok', ESTIMATED: 'estimated',
  MISSING_VALUE: 'missing_value', MISSING_QUANTITY: 'missing_quantity',
  OUTLIER: 'outlier', BOUNDARY_HISTORIC: 'boundary',
};

function ViewQuality({ summary, database }) {
  const filtered = window.applyFilters(summary || {}, database);
  const flags    = filtered.qualityFlags;
  const ts       = filtered.qualityTs;
  const total    = flags.reduce((s, f) => s + f.count, 0) || 1;
  const okFlag   = flags.find(f => f.id === 'OK');
  const okCount  = okFlag ? okFlag.count : 0;

  const flagSet = new Set(flags.map(f => f.id));
  // Restrict per-product breakdown to selected products AND selected flags.
  // We zero out unselected flag columns and re-normalize each row.
  const selectedProductNames = new Set(
    filtered.selectedProducts
      .map(c => (filtered.products.find(p => p.code === c) || {}).name)
      .filter(Boolean)
  );
  const qaByProduct = filtered.qualityByProduct
    .filter(r => selectedProductNames.has(r.name))
    .map(r => {
      const row = { code: r.code, name: r.name };
      let sum = 0;
      window.QUALITY_FLAGS.forEach(f => {
        const v = flagSet.has(f.id) ? (r[f.id] || 0) : 0;
        row[f.id] = v; sum += v;
      });
      // re-normalize to 100% of the selected flag world
      if (sum > 0) window.QUALITY_FLAGS.forEach(f => { row[f.id] = row[f.id] / sum; });
      return row;
    });

  // Restrict geographic quality map to selected UFs. null = no filter (all);
  // explicit empty = none (consistent with the data layer).
  const stateSet = (summary && summary.states != null)
    ? new Set(summary.states) : null;
  const qaByUf = filtered.qualityByUf.filter(u => !stateSet || stateSet.has(u.uf));

  return (
    <>
      {/* Flag KPI strip */}
      <div className="qa-flag-row">
        {flags.length === 0 ? (
          <div className="qa-flag-card" style={{ gridColumn: '1 / -1' }}>
            <span className="qa-flag-label">Nenhuma flag selecionada nos filtros.</span>
          </div>
        ) : flags.map(f => (
          <div key={f.id} className="qa-flag-card">
            <div className="qa-flag-head">
              <span className="qa-dot" style={{ background: f.color }}></span>
              <span className="qa-flag-label">{f.label}</span>
            </div>
            <div className="qa-flag-val tnum" style={{ color: f.id === 'OK' ? 'var(--ok)' : 'var(--fg-1)' }}>
              {window.fmtPct(f.share)}
            </div>
            <div className="qa-flag-sub tnum">
              {f.count.toLocaleString('pt-BR')} linhas
            </div>
          </div>
        ))}
      </div>

      {/* Quality over time */}
      <div className="card">
        <window.SectionHeader
          overline="Evolução temporal · qualidade dos dados"
          title={`% de linhas íntegras (flag = OK) · ${filtered.yearStart}–${filtered.yearEnd}`}
          action={
            <span className="caption">
              {okCount ? okCount.toLocaleString('pt-BR') : '—'} de {total.toLocaleString('pt-BR')} linhas íntegras
            </span>
          }
        />
        {okFlag ? (
          <window.LineChart
            data={ts.map(d => ({ y: d.y, v: d.ok * 100 }))}
            label="% OK"
            valueKey="v"
            color="var(--ok)"
            height={240}
          />
        ) : (
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Flag <code>OK</code> não está entre as selecionadas nos filtros.
          </p>
        )}
      </div>

      {/* Quality flag distribution by product */}
      <div className="card">
        <window.SectionHeader
          overline={`Distribuição de flags · ${filtered.yearEnd}`}
          title="Por produto"
          action={<span className="caption">{qaByProduct.length} de {filtered.qualityByProduct.length} produtos</span>}
        />
        {qaByProduct.length === 0 ? (
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Nenhum produto selecionado nos filtros.
          </p>
        ) : (
          <window.FlagBars rows={qaByProduct} flags={flags} labelKey="name" />
        )}
        <div className="qa-legend">
          {flags.map(f => (
            <span key={f.id} className="qa-legend-item">
              <span className="qa-dot" style={{ background: f.color }}></span>
              {f.label}
            </span>
          ))}
        </div>
      </div>

      {/* Quality by UF (geo bancos only) */}
      {filtered.qualityByUf.length > 0 && (
      <div className="card">
        <window.SectionHeader
          overline={`Qualidade geográfica · ${filtered.yearEnd}`}
          title="% de linhas não-íntegras por UF"
          action={<span className="caption">{qaByUf.length} de {filtered.qualityByUf.length} UFs</span>}
        />
        <window.BrazilTileMap data={qaByUf.map(u => ({ ...u, v: Math.round(u.not_ok * 1000) / 10 }))} valueKey="v" label="% ≠ OK" />
      </div>
      )}

      {/* Stacked area of flag share over time */}
      {flags.length > 0 && (
        <div className="card">
          <window.SectionHeader
            overline="Composição temporal · flags"
            title={`Share por flag · ${filtered.yearStart}–${filtered.yearEnd}`}
          />
          <window.StackedArea
            series={flags.slice().reverse().map(f => ({
              code: f.id,
              name: f.label,
              color: f.color,
              data: ts.map(d => ({ y: d.y, v: (d[QTS_KEY[f.id] || f.id.toLowerCase()] || 0) * 100 })),
            }))}
            valueKey="v"
            label="% linhas"
            height={260}
          />
          <div className="qa-legend">
            {flags.map(f => (
              <span key={f.id} className="qa-legend-item">
                <span className="qa-dot" style={{ background: f.color }}></span>
                {f.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

window.ViewQuality = ViewQuality;
