// ViewsMultiSource.jsx — the four analytical multi-source perspectives.
// All read through crossAnalytics.js contracts; all are self-contained
// (own commodity selector), since unlike "Cruzamento entre fontes" they
// don't need a lifted multi-series selection. Charts are reused as-is.

const { useState: useMSState } = React;

// Shared commodity selector (single-select; null = whole basket).
function CrossProductPicker({ value, onChange }) {
  const prods = window.PRODUCTS || [];
  return (
    <div className="pp-selector">
      <span className="pp-selector-label">Commodity</span>
      <div className="pp-chips">
        <button className={'pp-chip ' + (!value ? 'on' : '')}
          onClick={() => onChange(null)}
          style={!value ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}>
          Cesta completa
        </button>
        {prods.map(p => {
          const on = value === p.code;
          return (
            <button key={p.code}
              className={'pp-chip ' + (on ? 'on' : '')}
              onClick={() => onChange(p.code)}
              style={on ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}
              title={p.name}>
              <span className={'pp-chip-fam ' + p.family}></span>{p.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const msNum = window.numBR, msPct = window.pctBR;

// ── (1) Export coefficient ──────────────────────────────────────────────────
function ViewExportCoef({ view }) {
  const [product, setProduct] = useMSState(null);
  const data = window.exportCoefficient(product);
  const banco = window.crossPreviewBanco(view);
  const ranked = data.byUf.filter(u => u.production > 0).sort((a, b) => b.coefPct - a.coefPct);
  const top = ranked[0], bottom = ranked[ranked.length - 1];

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco} capabilityNote="Produção é real (IBGE); a parcela exportada por UF entra como demonstração até o MDIC ser ligado." />}
      <CrossProductPicker value={product} onChange={setProduct} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Coeficiente nacional" value={msPct(data.national.coefPct)} sub="do produzido segue p/ exportação" />
        <window.KpiCardSpark label="UF mais exportadora" value={top?.uf || '—'} sub={`${msPct(top?.coefPct || 0)} da produção`} />
        <window.KpiCardSpark label="UF mais interna" value={bottom?.uf || '—'} sub={`${msPct(bottom?.coefPct || 0)} exportado`} />
        <window.KpiCardSpark label="Produção considerada" value={msNum(data.national.production) + ' mil t'} sub={`${ranked.length} ${ranked.length === 1 ? 'UF' : 'UFs'} com produção`} />
      </div>

      <div className="card">
        <window.SectionHeader overline="Orientação exportadora · por UF" title="Quanto da produção de cada estado vai para fora"
          action={<span className="caption">% exportado · IBGE × MDIC</span>} />
        <window.BrazilTileMap data={data.byUf} valueKey="coefPct" label="% exportado" />
      </div>

      <div className="card">
        <window.SectionHeader overline="Coeficiente nacional no tempo" title="Evolução da orientação exportadora"
          action={<span className="caption">1997–2024 · valores ilustrativos</span>} />
        <window.LineChart data={data.timeseries} valueKey="v" label="%" color="var(--embrapa-green)" height={260} />
      </div>

      <div className="card">
        <window.SectionHeader overline="Ranking · maior orientação exportadora" title="UFs por coeficiente" />
        <div className="pc-table-wrap">
          <table className="pc-table">
            <thead><tr><th>UF</th><th className="num">Produção (mil t)</th><th className="num">Exportado (mil t)</th><th className="num">Coeficiente</th></tr></thead>
            <tbody>
              {ranked.slice(0, 10).map(u => (
                <tr key={u.uf}>
                  <td>{u.name} <small style={{ color: 'var(--fg-3)' }}>{u.uf}</small></td>
                  <td className="num tnum">{msNum(u.production, 1)}</td>
                  <td className="num tnum">{msNum(u.exportV, 1)}</td>
                  <td className="num tnum" style={{ color: 'var(--embrapa-green-darker)', fontWeight: 600 }}>{msPct(u.coefPct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── (2) Brazil in the world market ─────────────────────────────────────
function ViewMarketShare({ view }) {
  const [product, setProduct] = useMSState(null);
  const data = window.marketShare(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const first = data.series[0];
  const peak = data.series.reduce((m, d) => d.share > m.share ? d : m, data.series[0]);
  const shareTs = data.series.map(d => ({ y: d.y, v: d.share }));

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco} capabilityNote="Exportação brasileira e total mundial entram como demonstração até MDIC e UN Comtrade serem ligados." />}
      <CrossProductPicker value={product} onChange={setProduct} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Participação atual" value={msPct(last?.share)} sub={`${last?.y} · do mercado mundial`} />
        <window.KpiCardSpark label="Pico histórico" value={msPct(peak?.share)} sub={`em ${peak?.y}`} />
        <window.KpiCardSpark label="Variação na janela" value={window.fmtSigned((last?.share || 0) - (first?.share || 0), 1, ' p.p.')} deltaPositive={(last?.share || 0) >= (first?.share || 0)} sub={`${first?.y}–${last?.y}`} />
        <window.KpiCardSpark label="Exportação BR" value={'US$ ' + msNum(last?.br, 1) + ' bi'} sub={`mundo: US$ ${msNum(last?.world)} bi`} />
      </div>

      <div className="card">
        <window.SectionHeader overline="Participação no mercado mundial" title="Fração brasileira da exportação global"
          action={<span className="caption">% · MDIC ÷ UN Comtrade</span>} />
        <window.LineChart data={shareTs} valueKey="v" label="% do mundo" color="var(--viz-1)" height={280} />
      </div>

      <div className="card">
        <window.SectionHeader overline="Participação por commodity · último ano" title="Onde o Brasil pesa mais no mundo" />
        <window.BarChart data={data.byProduct.slice(0, 10).map(p => ({ name: p.name, value: p.share }))} valueKey="value" color="var(--viz-1)" label="% do mundo" height={300} />
      </div>
    </>
  );
}

// ── (3) Price: farm-gate vs. FOB ──────────────────────────────────────
function ViewPriceSpread({ view }) {
  const [product, setProduct] = useMSState(null);
  const data = window.priceSpread(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const markupTs = data.series.map(d => ({ y: d.y, v: d.markup }));
  const lineSeries = [
    { name: 'Preço de exportação (FOB)', color: 'var(--viz-3)', data: data.series.map(d => ({ y: d.y, v: d.fob })) },
    { name: 'Preço na porteira (produção)', color: 'var(--viz-2)', data: data.series.map(d => ({ y: d.y, v: d.gate })) },
  ];

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco} capabilityNote="Preço de exportação entra como demonstração até o MDIC ser ligado; o preço na porteira deriva da produção real (IBGE)." />}
      <CrossProductPicker value={product} onChange={setProduct} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Preço FOB atual" value={'US$ ' + msNum(last?.fob, 2) + '/kg'} sub={`${last?.y} · no porto`} />
        <window.KpiCardSpark label="Preço na porteira" value={'US$ ' + msNum(last?.gate, 2) + '/kg'} sub="na produção" />
        <window.KpiCardSpark label="Markup" value={'×' + msNum(last?.markup, 1)} sub="FOB ÷ porteira" />
        <window.KpiCardSpark label="Spread" value={'US$ ' + msNum(last?.spread, 2) + '/kg'} sub="valor agregado entre porteira e porto" />
      </div>

      <div className="card">
        <window.SectionHeader overline="Porteira vs. porto · US$/kg" title="Onde o valor é capturado"
          action={<span className="caption">IBGE × MDIC</span>} />
        <window.MultiLineChart series={lineSeries} valueKey="v" label="US$/kg" height={300} />
        <div className="pc-legend">
          {lineSeries.map(s => (
            <span key={s.name} className="pc-legend-item"><span className="pc-legend-dot" style={{ background: s.color }}></span>{s.name}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <window.SectionHeader overline="Markup no tempo" title="Quantas vezes o porto vale a porteira"
          action={<span className="caption">× · FOB ÷ porteira</span>} />
        <window.LineChart data={markupTs} valueKey="v" label="×" color="var(--embrapa-blue)" height={240} />
      </div>
    </>
  );
}

// ── (4) Espelho comercial ─────────────────────────────────────────────
function ViewMirror({ view }) {
  const [product, setProduct] = useMSState(null);
  const data = window.tradeMirror(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const avgDisc = data.discrepancy.reduce((s, d) => s + d.v, 0) / (data.discrepancy.length || 1);
  const lineSeries = [
    { name: 'MDIC · SECEX', color: 'var(--viz-1)', data: data.series.map(d => ({ y: d.y, v: d.mdic })) },
    { name: 'UN Comtrade (Brasil)', color: 'var(--viz-3)', data: data.series.map(d => ({ y: d.y, v: d.comtrade })) },
    { name: 'Reportado pelos parceiros', color: 'var(--viz-9)', data: data.series.map(d => ({ y: d.y, v: d.partners })) },
  ];

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco} capabilityNote="As três leituras da mesma exportação entram como demonstração até MDIC e UN Comtrade serem ligados." />}
      <CrossProductPicker value={product} onChange={setProduct} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Divergência média" value={msPct(avgDisc)} sub="entre a maior e a menor fonte" />
        <window.KpiCardSpark label="Maior reporte" value="Parceiros" sub="tendem a registrar mais que a origem" />
        <window.KpiCardSpark label="Exportação MDIC" value={'US$ ' + msNum(last?.mdic, 1) + ' bi'} sub={`${last?.y}`} />
        <window.KpiCardSpark label="Janela" value="1997–2024" sub="cobertura comparável" />
      </div>

      <div className="card">
        <window.SectionHeader overline="A mesma exportação, três fontes" title="MDIC × Comtrade × parceiros"
          action={<span className="caption">US$ bi · valores ilustrativos</span>} />
        <window.MultiLineChart series={lineSeries} valueKey="v" label="US$ bi" height={300} />
        <div className="pc-legend">
          {lineSeries.map(s => (
            <span key={s.name} className="pc-legend-item"><span className="pc-legend-dot" style={{ background: s.color }}></span>{s.name}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <window.SectionHeader overline="Divergência no tempo" title="Quão distantes estão as fontes"
          action={<span className="caption">% · (máx − mín) ÷ média</span>} />
        <window.LineChart data={data.discrepancy} valueKey="v" label="% divergência" color="var(--status-warn)" height={240} />
        <p className="caption" style={{ padding: '10px 2px 2px' }}>
          Divergências persistentes apontam diferenças de metodologia, defasagem de revisão ou cobertura — um diagnóstico que nenhuma fonte isolada revela.
        </p>
      </div>
    </>
  );
}

Object.assign(window, { CrossProductPicker, ViewExportCoef, ViewMarketShare, ViewPriceSpread, ViewMirror });
