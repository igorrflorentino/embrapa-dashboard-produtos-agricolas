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

  // Real per-UF ranking for the active product. The "Onde X é produzido" chart
  // previously FABRICATED the per-UF split (a sine jitter over a synthetic
  // affinity table). Fetch the true per-product × UF breakdown from
  // /api/product-uf (Gold grouped by product × UF, already in the active currency,
  // honouring the year filter). Hooks sit ABOVE the early-return so hook order is
  // stable across renders (Rules of Hooks).
  const [ufRank, setUfRank] = usePPState({ rows: null, loading: true });
  React.useEffect(() => {
    // Only fetch when the UF card will actually render (hasGeo) — skip the needless
    // request for non-geo bancos (e.g. COMTRADE) where the card is gated off.
    if (!activeCode || !hasGeo) return undefined;
    let alive = true;
    setUfRank({ rows: null, loading: true });
    const qs = new URLSearchParams({
      banco: database,
      code: activeCode,
      currency: conv.currency,
      correction: conv.correction,
    });
    if (summary?.startDate) qs.set('startDate', summary.startDate);
    if (summary?.endDate) qs.set('endDate', summary.endDate);
    fetch(`/api/product-uf?${qs}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive) setUfRank({ rows: (d && d.uf) || [], loading: false });
      })
      .catch(() => {
        if (alive) setUfRank({ rows: [], loading: false });
      });
    return () => {
      alive = false;
    };
  }, [database, activeCode, hasGeo, conv.currency, conv.correction, summary?.startDate, summary?.endDate, setUfRank]);

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
  // Family-aware axis + multiplier (mass→t, volume→m³, count→cabeças/un). The old
  // binary "mass ? … : volume" would label a livestock headcount in m³.
  const AXIS_FN = { mass: window.massAxisLabel, volume: window.volumeAxisLabel, count: window.countAxisLabel };
  const QMUL_FN = { mass: window.massQtyMul,    volume: window.volumeQtyMul,    count: window.countQtyMul };
  const FAM_COLOR = { mass: 'var(--viz-2)', volume: 'var(--viz-4)', count: 'var(--viz-9)' };
  const unitAx = (AXIS_FN[family] || window.massAxisLabel)(conv);
  const qtyMul = (QMUL_FN[family] || window.massQtyMul)(conv);
  const qColor = FAM_COLOR[family] || 'var(--viz-2)';

  // Per-product series (PRODUCT_TS.v in base-currency mi, .q in family display unit)
  const raw = filtered.allProductTS[activeCode];
  const yearStart = filtered.yearStart, yearEnd = filtered.yearEnd;
  const win = raw.filter(d => d.y >= yearStart && d.y <= yearEnd);

  // A herd headcount (PPM measure_kind='stock') is a STOCK with NO monetary value —
  // value / implicit price / market-share-by-value are meaningless for it. Detect via
  // the explicit discriminator when present, else fall back to "no positive value in
  // the window" so a value-less series is never shown a fabricated R$ 0 price.
  const isStock = prod.measure_kind ? prod.measure_kind === 'stock' : !win.some(d => d.v > 0);

  // Basket totals per year: VALUE (flow share) and same-family QUANTITY (stock share).
  // The efetivo share of a STOCK is among OTHER STOCKS only — egg/milk count-FLOWS are
  // not part of the efetivo, so they must not inflate the headcount denominator.
  const totalByYear = {}, totalQByYear = {};
  Object.entries(filtered.productTS).forEach(([code, series]) => {
    const p = filtered.products.find(x => x.code === code);
    const inQtyDenom = p && p.family === family
      && (!isStock || p.measure_kind === 'stock');
    series.forEach(d => {
      totalByYear[d.y] = (totalByYear[d.y] || 0) + d.v;
      if (inQtyDenom && d.q != null) totalQByYear[d.y] = (totalQByYear[d.y] || 0) + d.q;
    });
  });

  // Implicit price = value ÷ quantity, both in their displayed unit. The quantity
  // series uses the family-aware qtyMul, so the price divides by the SAME d.q * qtyMul
  // (avoids the 1000× m³ inflation the old hardcoded ×1e3 caused for volume products).
  const valueSeries = win.map(d => ({ y: d.y, v: d.v * 1e6 * cvf }));      // absolute currency
  const qtySeries   = win.map(d => ({ y: d.y, q: d.q * qtyMul }));                   // display unit (×mul)
  const priceSeries = win.map(d => ({ y: d.y, v: (d.q * qtyMul) ? (d.v * 1e6 * cvf) / (d.q * qtyMul) : 0 })); // moeda/unidade
  // Share: by VALUE for a flow; by same-family QUANTITY for a value-less stock.
  const shareSeries = win.map(d => ({
    y: d.y,
    v: isStock
      ? (totalQByYear[d.y] ? (d.q / totalQByYear[d.y]) * 100 : 0)
      : (totalByYear[d.y] ? (d.v / totalByYear[d.y]) * 100 : 0),
  }));

  const last = win[win.length - 1] || { v: 0, q: 0 };
  const prev = win[win.length - 2] || last;
  const lastValAbs = last.v * 1e6 * cvf;
  const prevValAbs = prev.v * 1e6 * cvf;
  const deltaV = prevValAbs ? ((lastValAbs - prevValAbs) / prevValAbs) * 100 : 0;
  const deltaQ = prev.q ? ((last.q - prev.q) / prev.q) * 100 : 0;
  const lastPrice = (last.q * qtyMul) ? (last.v * 1e6 * cvf) / (last.q * qtyMul) : 0;
  const lastShare = isStock
    ? (totalQByYear[last.y] ? (last.q / totalQByYear[last.y]) * 100 : 0)
    : (totalByYear[last.y] ? (last.v / totalByYear[last.y]) * 100 : 0);
  // Historical peak headcount (drives the stock KPI that replaces "Valor")
  const peak = win.reduce((m, d) => (d.q > m.q ? d : m), win[0] || { y: last.y, q: 0 });

  // Top-10 producing/raising UFs from the REAL per-UF ranking. A value-less stock ranks
  // by headcount (q_count) instead of an all-zero value; the bar measure (_m) is value
  // for a flow, or the family-scaled quantity for a stock.
  const ufMeasure = isStock ? 'q_count' : 'value';
  const ufRows = (ufRank.rows || []).slice()
    .sort((a, b) => (b[ufMeasure] || 0) - (a[ufMeasure] || 0)).slice(0, 10)
    .map(u => ({ ...u, _m: isStock ? (u.q_count || 0) * qtyMul : u.value }));
  const ufScaled = window.scaleSeries(
    ufRows, Math.max(...ufRows.map(u => u._m), 0), conv, '_m', isStock ? unitAx : fx.symbol,
  );

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

      {/* KPI strip — for a value-less stock (herd) the Valor/Preço cards are replaced
          by Efetivo + Pico histórico, since a headcount has no money. */}
      <div className="kpi-row">
        {isStock ? (
          <window.KpiCardSpark
            label={<>Efetivo · <window.UnitFamilyTag family={family} conv={conv}/></>}
            value={window.formatCountQty(last.q, conv)}
            delta={window.fmtSigned(deltaQ)}
            deltaPositive={last.q >= prev.q}
            sub={`${last.y} vs. ${prev.y}`}
            spark={win.slice(-12).map(d => ({ y: d.y, q: d.q }))}
            sparkKey="q"
            sparkColor={qColor}
          />
        ) : (
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
        )}
        {isStock ? (
          <window.KpiCardSpark
            label="Pico histórico"
            value={window.formatCountQty(peak.q, conv)}
            sub={`em ${peak.y}`}
            spark={win.slice(-12).map(d => ({ y: d.y, q: d.q }))}
            sparkKey="q"
            sparkColor="var(--viz-7)"
          />
        ) : (
          <window.KpiCardSpark
            label={<>Quantidade · <window.UnitFamilyTag family={family} conv={conv}/></>}
            value={(last.q * qtyMul).toLocaleString('pt-BR', { maximumFractionDigits: 0 }) + ' ' + unitAx}
            delta={window.fmtSigned(deltaQ)}
            deltaPositive={last.q >= prev.q}
            sub={`${last.y} vs. ${prev.y}`}
            spark={win.slice(-12).map(d => ({ y: d.y, q: d.q }))}
            sparkKey="q"
            sparkColor={qColor}
          />
        )}
        {!isStock && (
          <window.KpiCardSpark
            label="Preço médio implícito"
            value={fx.symbol + ' ' + lastPrice.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' /' + prod.unit}
            sub="valor ÷ quantidade"
            spark={priceSeries.slice(-12)}
            sparkKey="v"
            sparkColor="var(--viz-7)"
          />
        )}
        <window.KpiCardSpark
          label={isStock ? 'Participação no efetivo' : 'Participação na cesta'}
          value={window.fmtPct(lastShare / 100)}
          sub={`${filtered.selectedProducts.length} ${filtered.selectedProducts.length === 1 ? 'produto' : 'produtos'} na cesta`}
          spark={shareSeries.slice(-12)}
          sparkKey="v"
          sparkColor="var(--viz-5)"
        />
      </div>

      {isStock ? (
        <>
          {/* Stock (herd): efetivo + participação, no value/price (a headcount has no money) */}
          <div className="grid-2">
            <div className="card">
              <window.SectionHeader
                overline={<>Série do efetivo · <window.UnitFamilyTag family={family} conv={conv}/></>}
                title={`${prod.name} · efetivo (${qtyScaled.label})`}
              />
              <window.LineChart data={qtyScaled.data} label={qtyScaled.label} valueKey="q" color={qColor} height={230} trend />
            </div>
            <div className="card">
              <window.SectionHeader
                overline="Participação no efetivo · % do total da cesta"
                title={`Participação de ${prod.name} no efetivo`}
              />
              <window.LineChart data={shareSeries} label="% do efetivo" valueKey="v" color="var(--viz-5)" height={230} />
            </div>
          </div>
          <p className="caption" style={{ margin: '4px 2px 0' }}>
            ⓘ O efetivo dos rebanhos é um <strong>estoque</strong> (nº de cabeças), não uma produção: não tem
            valor monetário nem preço, e <strong>não deve ser somado entre espécies</strong>.
          </p>
        </>
      ) : (
        <>
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
              <window.LineChart data={qtyScaled.data} label={qtyScaled.label} valueKey="q" color={qColor} height={230} />
            </div>
          </div>

          {/* Implicit price + market share */}
          <div className="grid-2">
            <div className="card">
              <window.SectionHeader
                overline="Preço médio implícito · valor ÷ quantidade"
                title={`${fx.symbol} por ${prod.unit} · ${yearStart}–${yearEnd}`}
              />
              <window.LineChart data={priceSeries} label={fx.symbol + '/' + prod.unit} valueKey="v" color="var(--viz-7)" height={220} trend />
            </div>
            <div className="card">
              <window.SectionHeader
                overline="Participação na cesta · % do valor total"
                title={`Participação de ${prod.name} na cesta`}
              />
              <window.LineChart data={shareSeries} label="% da cesta" valueKey="v" color="var(--viz-5)" height={220} />
            </div>
          </div>
        </>
      )}

      {/* UF ranking + ficha técnica */}
      <div className="grid-2">
        {hasGeo && (
        <div className="card">
          <window.SectionHeader
            overline={`Ranking de UFs ${isStock ? 'criadoras' : 'produtoras'} · ${yearStart}–${yearEnd}`}
            title={`Onde ${prod.name} ${isStock ? 'é criado' : 'é produzido'}`}
            action={<span className="caption">Top 10 · {ufScaled.label}</span>}
          />
          {ufRank.loading ? (
            <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>
              Carregando distribuição por UF…
            </p>
          ) : ufRows.length ? (
            <window.BarChart data={ufScaled.data} valueKey="_m" color={isStock ? qColor : 'var(--viz-2)'} height={320} />
          ) : (
            <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>
              Sem dados por UF para este produto.
            </p>
          )}
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
            {isStock && <><dt>Tipo de medida</dt><dd>Estoque (efetivo)</dd></>}
            <dt>Cobertura temporal</dt><dd className="tnum">{yearStart}–{yearEnd}</dd>
            {isStock
              ? <><dt>Efetivo ({last.y})</dt><dd>{window.formatCountQty(last.q, conv)}</dd></>
              : <><dt>Valor ({last.y})</dt><dd>{window.formatValue(last.v * 1e6, conv)}</dd></>}
            <dt>{isStock ? 'Participação no efetivo' : 'Participação na cesta'}</dt><dd>{window.fmtPct(lastShare / 100)}</dd>
            {qaRow && <><dt>Linhas íntegras (OK)</dt><dd>{window.fmtPct(qaRow.OK)}</dd></>}
            {qaRow && !isStock && <><dt>Valor ausente</dt><dd>{window.fmtPct(qaRow.MISSING_VALUE)}</dd></>}
            {qaRow && isStock && qaRow.MISSING_QUANTITY != null && <><dt>Quantidade ausente</dt><dd>{window.fmtPct(qaRow.MISSING_QUANTITY)}</dd></>}
          </dl>
        </div>
      </div>
    </>
  );
}

window.ViewProductProfile = ViewProductProfile;
