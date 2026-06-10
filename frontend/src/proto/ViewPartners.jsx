// ViewPartners — trading-partner rankings (country or UF). Generic via
// the partnerData contract. Synthetic preview until the banco is live.

function ViewPartners({ summary, conventions, database }) {
  const banco = window.bancoById(database);
  const data  = window.partnerData(database, summary);
  const total = data.partners.reduce((s, p) => s + p.value, 0) || 1;
  const top = data.partners[0];
  const fmt = (v) => data.unit + ' ' + (v >= 1000 ? (v / 1000).toFixed(1).replace('.', ',') + ' bi' : v + ' mi');
  const max = Math.max(...data.partners.map(p => p.value), 1);

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco}
        capabilityNote="Rankings de parceiros exigem a dimensão de parceiro comercial, ainda não disponível nesta fonte." />}

      <div className="kpi-row">
        <window.KpiCardSpark label={`Maior ${data.flowLabel}`} value={top?.name || '—'} sub={fmt(top?.value || 0)} />
        <window.KpiCardSpark label="Parceiros mapeados" value={data.partners.length} sub={`fluxo total ${fmt(total)}`} />
        <window.KpiCardSpark label="Concentração top-3" value={window.fmtPct(data.partners.slice(0,3).reduce((s,p)=>s+p.value,0)/total)} sub="do fluxo total" />
        <window.KpiCardSpark label="Granularidade" value={banco?.scope || '—'} sub={banco?.domain || ''} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline={`Ranking · ${data.flowLabel}`}
          title="Maiores parceiros comerciais"
          action={<span className="caption">{data.unit} · exportação + importação</span>}
        />
        <div className="ptn-list">
          {data.partners.map((p, i) => (
            <div key={p.name} className="ptn-row">
              <span className="ptn-rank tnum">#{i + 1}</span>
              <span className="ptn-name">{p.name}</span>
              <div className="ptn-bars">
                <div className="ptn-bar exp" style={{ width: (p.exp / max * 100) + '%' }} title={'Exportação ' + fmt(p.exp)}></div>
                <div className="ptn-bar imp" style={{ width: (p.imp / max * 100) + '%' }} title={'Importação ' + fmt(p.imp)}></div>
              </div>
              <span className="ptn-val tnum">{fmt(p.value)}</span>
            </div>
          ))}
        </div>
        <div className="ptn-legend">
          <span className="ptn-legend-item"><span className="ptn-legend-dot exp"></span>Exportação</span>
          <span className="ptn-legend-item"><span className="ptn-legend-dot imp"></span>Importação</span>
        </div>
      </div>
    </>
  );
}

window.ViewPartners = ViewPartners;
