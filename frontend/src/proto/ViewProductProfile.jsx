// ViewProductProfile — deep dive into a SINGLE commodity.
// Only meaningful for bancos that provide the 'product' capability.
// Honours active filters: the product selector is limited to the
// basket (filtered.selectedProducts); value/qty respect conventions.

const { useState: usePPState } = React;

function ViewProductProfile({ families, summary, database, conventions }) {
  const conv     = conventions || window.DEFAULT_CONVENTIONS;
  const monLabel = window.conventionMonetaryLabel(conv);
  const fx       = window.CURRENCY_FX[conv.currency];
  const cvf      = window.convFactor(conv);   // base-aware value factor (corr × rate ÷ baseRate)

  const filtered = window.applyFilters(summary || {}, database);
  const available = filtered.selectedProducts.filter(c => filtered.allProductTS[c]);
  const hasGeo = filtered.ufDataFull.length > 0;
  // Code scheme label — declared per banco in bancos.js (dimensions.product),
  // not branched on bancoId here.
  const codeLabel = window.bancoDim(database, 'product').codeLabel || 'Código';

  // Selected product (default = largest by latest value within basket)
  const defaultCode = (() => {
    if (!available.length) return null;
    return available
      .map(c => ({ c, v: filtered.allProductTS[c].slice(-1)[0]?.v || 0 }))
      .sort((a, b) => b.v - a.v)[0].c;
  })();
  const [code, setCode] = usePPState(defaultCode);
  const activeCode = (code && available.includes(code)) ? code : defaultCode;

  if (!activeCode) {
    return (
      <div className="card subtle">
        <p className="caption" style={{ padding: '20px 4px', textAlign: 'center' }}>
          Nenhum produto disponível na seleção atual. Ajuste os filtros para escolher uma commodity.
        </p>
      </div>
    );
  }

  const prod   = filtered.products.find(p => p.code === activeCode);
  const family = prod.family;
  const unitAx = family === 'mass' ? window.massAxisLabel(conv) : window.volumeAxisLabel(conv);
  const qtyMul = family === 'mass' ? window.massQtyMul(conv) : window.volumeQtyMul(conv);

  // Per-product series (PRODUCT_TS.v in base-currency mi, .q in thousands of native unit)
  const raw = filtered.allProductTS[activeCode];
  const yearStart = filtered.yearStart, yearEnd = filtered.yearEnd;
  const win = raw.filter(d => d.y >= yearStart && d.y <= yearEnd);

  // Total basket value per year (for market share within the cesta)
  const totalByYear = {};
  Object.values(filtered.productTS).forEach(series => {
    series.forEach(d => { totalByYear[d.y] = (totalByYear[d.y] || 0) + d.v; });
  });

  // Build display series
  const valueSeries = win.map(d => ({ y: d.y, v: d.v * 1e6 * cvf }));      // absolute currency
  const qtySeries   = win.map(d => ({ y: d.y, q: d.q * qtyMul }));                   // native unit (×mul)
  const priceSeries = win.map(d => ({ y: d.y, v: (d.v * 1e6 * cvf) / (d.q * 1e3) })); // moeda/unidade
  const shareSeries = win.map(d => ({ y: d.y, v: totalByYear[d.y] ? (d.v / totalByYear[d.y]) * 100 : 0 }));

  const last = win[win.length - 1] || { v: 0, q: 0 };
  const prev = win[win.length - 2] || last;
  const lastValAbs = last.v * 1e6 * cvf;
  const prevValAbs = prev.v * 1e6 * cvf;
  const deltaV = prevValAbs ? ((lastValAbs - prevValAbs) / prevValAbs) * 100 : 0;
  const lastPrice = (last.v * 1e6 * cvf) / (last.q * 1e3);
  const lastShare = totalByYear[last.y] ? (last.v / totalByYear[last.y]) * 100 : 0;

  // Per-product UF ranking — deterministic allocation of the product's
  // latest national value across UFs, biased by region affinity (data.js →
  // window.PRODUCT_REGION_AFFINITY, the single source) so the ranking is
  // plausible and product-specific.
  const aff = (window.PRODUCT_REGION_AFFINITY || {})[activeCode] || {};
  const ufAlloc = (() => {
    const seedChar = activeCode.charCodeAt(4);
    const weighted = filtered.ufDataFull.map((u, i) => {
      const base = u.value;
      const regionMul = aff[u.region] || 0.5;
      const jitter = 0.8 + 0.4 * Math.abs(Math.sin(i * 1.7 + seedChar));
      return { uf: u.uf, name: u.name, region: u.region, w: base * regionMul * jitter };
    });
    const totalW = weighted.reduce((s, u) => s + u.w, 0) || 1;
    const prodValAbs = lastValAbs;
    return weighted
      .map(u => ({ ...u, value: (u.w / totalW) * prodValAbs }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  })();
  const ufScaled = window.scaleSeries(ufAlloc, Math.max(...ufAlloc.map(u => u.value), 0), conv, 'value', fx.symbol);

  // Quality for this product (may be absent from the curated subset)
  const qaRow = filtered.qualityByProduct.find(r => r.code === activeCode);

  // Auto-scale value/qty/price series for charts
  const valScaled = window.scaleSeries(valueSeries, Math.max(...valueSeries.map(d => d.v), 0), conv, 'v', fx.symbol);
  const qtyScaled = window.scaleSeries(qtySeries,  Math.max(...qtySeries.map(d => d.q), 0),  conv, 'q', unitAx);

  return (
    <>
      {/* Product selector */}
      <div className="pp-selector">
        <span className="pp-selector-label">Commodity em análise</span>
        <div className="pp-chips">
          {available.map(c => {
            const p = filtered.products.find(x => x.code === c);
            return (
              <button key={c}
                      className={'pp-chip ' + (c === activeCode ? 'on' : '')}
                      onClick={() => setCode(c)}>
                <span className={'pp-chip-fam ' + p.family}></span>
                {p.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* KPI strip */}
      <div className="kpi-row">
        <window.KpiCardSpark
          label={`Valor · ${monLabel}`}
          value={window.formatValue(last.v * 1e6, conv)}
          delta={window.fmtSigned(deltaV)}
          deltaPositive={deltaV >= 0}
          sub={`${last.y} vs. ${prev.y}`}
          spark={win.slice(-12).map(d => ({ y: d.y, v: d.v }))}
          sparkKey="v"
          sparkColor="var(--viz-1)"
        />
        <window.KpiCardSpark
          label={<>Quantidade · <window.UnitFamilyTag family={family} conv={conv}/></>}
          value={(last.q * qtyMul).toLocaleString('pt-BR', { maximumFractionDigits: 0 }) + ' ' + unitAx}
          delta={window.fmtSigned(prev.q ? ((last.q - prev.q) / prev.q) * 100 : 0)}
          deltaPositive={last.q >= prev.q}
          sub={`${last.y} vs. ${prev.y}`}
          spark={win.slice(-12).map(d => ({ y: d.y, q: d.q }))}
          sparkKey="q"
          sparkColor={family === 'mass' ? 'var(--viz-2)' : 'var(--viz-4)'}
        />
        <window.KpiCardSpark
          label="Preço médio implícito"
          value={fx.symbol + ' ' + lastPrice.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' /' + prod.unit}
          sub="valor ÷ quantidade"
          spark={priceSeries.slice(-12)}
          sparkKey="v"
          sparkColor="var(--viz-7)"
        />
        <window.KpiCardSpark
          label="Participação na cesta"
          value={window.fmtPct(lastShare / 100)}
          sub={`${filtered.selectedProducts.length} ${filtered.selectedProducts.length === 1 ? 'produto' : 'produtos'} na cesta`}
          spark={shareSeries.slice(-12)}
          sparkKey="v"
          sparkColor="var(--viz-5)"
        />
      </div>

      {/* Value + quantity series */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline={`Série de valor · ${monLabel}`}
            title={`${prod.name} · valor (${valScaled.label})`}
          />
          <window.LineChart data={valScaled.data} label={valScaled.label} valueKey="v" color="var(--viz-1)" height={230} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline={<>Série de quantidade · <window.UnitFamilyTag family={family} conv={conv}/></>}
            title={`${prod.name} · quantidade (${qtyScaled.label})`}
          />
          <window.LineChart data={qtyScaled.data} label={qtyScaled.label} valueKey="q" color={family === 'mass' ? 'var(--viz-2)' : 'var(--viz-4)'} height={230} />
        </div>
      </div>

      {/* Implicit price + market share */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline="Preço médio implícito · valor ÷ quantidade"
            title={`${fx.symbol} por ${prod.unit} · ${yearStart}–${yearEnd}`}
          />
          <window.LineChart data={priceSeries} label={fx.symbol + '/' + prod.unit} valueKey="v" color="var(--viz-7)" height={220} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline="Participação na cesta · % do valor total"
            title={`Participação de ${prod.name} na cesta`}
          />
          <window.LineChart data={shareSeries} label="% da cesta" valueKey="v" color="var(--viz-5)" height={220} />
        </div>
      </div>

      {/* UF ranking + ficha técnica */}
      <div className="grid-2">
        {hasGeo && (
        <div className="card">
          <window.SectionHeader
            overline={`Ranking de UFs produtoras · ${yearEnd}`}
            title={`Onde ${prod.name} é produzido`}
            action={<span className="caption">Top 10 · {ufScaled.label}</span>}
          />
          <window.BarChart data={ufScaled.data} valueKey="value" color="var(--viz-2)" height={320} />
        </div>
        )}
        <div className="card">
          <window.SectionHeader
            overline="Ficha técnica"
            title={prod.name}
          />
          <dl className="pp-spec">
            <dt>{codeLabel}</dt><dd className="tnum">{prod.code}</dd>
            <dt>Unidade nativa</dt><dd>{prod.unit} ({window.UNIT_FAMILIES[family].long})</dd>
            <dt>Família de unidade</dt><dd>{window.UNIT_FAMILIES[family].label}</dd>
            <dt>Cobertura temporal</dt><dd className="tnum">{yearStart}–{yearEnd}</dd>
            <dt>Valor ({last.y})</dt><dd>{window.formatValue(last.v * 1e6, conv)}</dd>
            <dt>Participação na cesta</dt><dd>{window.fmtPct(lastShare / 100)}</dd>
            {qaRow && <><dt>Linhas íntegras (OK)</dt><dd>{window.fmtPct(qaRow.OK)}</dd></>}
            {qaRow && <><dt>Valor ausente</dt><dd>{window.fmtPct(qaRow.MISSING_VALUE)}</dd></>}
          </dl>
        </div>
      </div>
    </>
  );
}

window.ViewProductProfile = ViewProductProfile;
