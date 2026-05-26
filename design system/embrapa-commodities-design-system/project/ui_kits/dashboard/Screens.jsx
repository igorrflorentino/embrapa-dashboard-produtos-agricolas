// Secondary screens — keep these light. The Overview is the hero recreation.

function ProductScreen({ filters }) {
  return (
    <div className="screen">
      <window.SectionHeader
        overline="Castanha-do-pará · IBGE PEVS 49101"
        title="Análise por produto"
        action={<button className="btn-secondary">Trocar produto</button>}
      />
      <div className="kpi-row">
        <window.KpiCard label="Valor real (IPCA)" value="R$ 379 mi" delta="+8,2%" deltaPositive={true} sub="vs. 2022" />
        <window.KpiCard label="Quantidade" value="32.480 t" delta="−1,4%" deltaPositive={false} sub="vs. 2022" />
        <window.KpiCard label="UFs produtoras" value="6" sub="PA, AM, AC, RO, MT, RR" />
        <window.KpiCard label="Concentração" value="62%" sub="Top 2 UFs (PA + AM)" />
      </div>
      <div className="card">
        <window.SectionHeader overline="Histórico" title="Castanha-do-pará — Valor real IPCA, R$ mi" />
        <window.LineChart
          data={window.OVERVIEW_TS.map(d => ({ y: d.y, v: d.v * 90 }))}
          valueKey="v" label="R$ mi" color="var(--viz-2)" height={220} />
      </div>
    </div>
  );
}

function GeoScreen() {
  return (
    <div className="screen">
      <window.SectionHeader
        overline="Distribuição geográfica · 2023"
        title="Produção por unidade federativa"
        action={<div className="seg"><button className="seg-opt on">Mapa</button><button className="seg-opt">Tabela</button></div>}
      />
      <div className="grid-2-alt">
        <div className="card map-card">
          <div className="map-placeholder">
            <window.Icon name="map" size={48}/>
            <p className="caption">Coroplético do Brasil (placeholder)<br/>Tonalidade verde por valor real IPCA.</p>
          </div>
        </div>
        <div className="card">
          <window.SectionHeader overline="Ranking" title="Top 8 estados" />
          <window.BarChart data={window.TOP_UFS} valueKey="value" color="var(--viz-1)" height={260} />
        </div>
      </div>
    </div>
  );
}

function QualityScreen() {
  const flags = [
    { f: 'OK', count: 18472, pct: 94.2, color: 'var(--embrapa-green)' },
    { f: 'MISSING_VALUE',    count: 712,  pct: 3.6, color: 'var(--status-warn)' },
    { f: 'MISSING_QUANTITY', count: 318,  pct: 1.6, color: 'var(--embrapa-blue)' },
    { f: 'INCOMPLETE',       count: 118,  pct: 0.6, color: 'var(--status-error)' },
  ];
  return (
    <div className="screen">
      <window.SectionHeader
        overline="data_quality_flag"
        title="Qualidade dos dados · 2023"
      />
      <div className="grid-2">
        {flags.map(f => (
          <div key={f.f} className="card flag-card">
            <div>
              <div className="overline">{f.f}</div>
              <div className="kpi-val tnum">{f.count.toLocaleString('pt-BR')}</div>
              <div className="caption">linhas · {f.pct}% do total</div>
            </div>
            <div className="flag-bar">
              <div style={{ width: f.pct + '%', background: f.color }}></div>
            </div>
          </div>
        ))}
      </div>
      <div className="card">
        <window.SectionHeader overline="Amostra com problemas" title="Linhas marcadas como não-OK" />
        <window.DataTable rows={window.SAMPLE_ROWS.filter(r => r.flag !== 'OK')} />
      </div>
    </div>
  );
}

Object.assign(window, { ProductScreen, GeoScreen, QualityScreen });
