// ViewPartners — trading-partner rankings (country or UF). Generic via
// the partnerData contract (real Gold data).
//
// The ranking dimension is switchable between Capital (valor US$), Volume (peso
// líquido) and Preço médio (US$/kg = valor ÷ peso). The metric is sent to the
// producer so the ranking is recomputed SERVER-SIDE (a niche high-unit-price
// buyer tops the price ranking but has a small total value — re-sorting a
// value-ranked page client-side would drop it). See serving/sql.trade_by_partner.

const _PARTNER_METRICS = [
  { id: 'value',  label: 'Capital',     field: 'value',  additive: true },
  { id: 'weight', label: 'Volume',      field: 'weight', additive: true },
  { id: 'price',  label: 'Preço médio', field: 'price',  additive: false },
];

const _nf = (v, d = 0) =>
  Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });

function ViewPartners({ summary, conventions, database }) {
  const [metric, setMetric] = window.React.useState('value');
  const banco = window.bancoById(database);
  const data  = window.partnerData(database, summary, metric);
  const spec  = _PARTNER_METRICS.find((m) => m.id === metric) || _PARTNER_METRICS[0];

  // How each metric formats a partner's measure for display.
  const fmtMoney = (v) =>
    data.unit + ' ' + (v >= 1000 ? _nf(v / 1000, 1) + ' bi' : _nf(v, v < 10 ? 2 : 0) + ' mi');
  const fmtMetric = (p) => {
    const v = p && p[spec.field];
    if (metric === 'value')  return fmtMoney(v || 0);
    if (metric === 'weight') return _nf((v || 0) * 1000) + ' t'; // mil t → t (pt-BR)
    return v == null ? '—' : 'US$ ' + _nf(v, 2) + '/kg';          // price (US$/kg)
  };

  const partners = data.partners || [];
  const valOf = (p) => (p && p[spec.field]) || 0; // price null → 0 (bar/scale only)
  const max = Math.max(...partners.map(valOf), spec.id === 'price' ? 0.0001 : 1);
  const top = partners[0];

  // top-3 concentration only makes sense for additive metrics (valor, peso); for
  // preço médio (a ratio) show the value range across the ranked partners instead.
  const sumField = partners.reduce((s, p) => s + valOf(p), 0) || 1;
  const kpi3 = spec.additive
    ? {
        label: 'Concentração top-3',
        value: window.fmtPct(partners.slice(0, 3).reduce((s, p) => s + valOf(p), 0) / sumField),
        sub: `do ${metric === 'value' ? 'fluxo' : 'volume'} total`,
      }
    : {
        label: 'Faixa de preço',
        value: partners.length
          ? `US$ ${_nf(Math.min(...partners.map(valOf).filter((v) => v > 0)), 2)}–${_nf(max, 2)}/kg`
          : '—',
        sub: 'menor – maior',
      };

  return (
    <>
      {/* Honest note when the origin-UF filter cannot apply (country-origin banco). */}
      <window.NotApplicableNote note={data.notApplicable} />
      {/* Distinct error state when the /api/partners fetch FAILED (not "0 parceiros"). */}
      <window.LoadErrorNote error={data.loadError} />

      <div className="kpi-row">
        <window.KpiCardSpark label={`Maior ${data.flowLabel}`} value={top?.name || '—'} sub={fmtMetric(top)} />
        <window.KpiCardSpark label="Parceiros mapeados" value={partners.length} sub={`por ${spec.label.toLowerCase()}`} />
        <window.KpiCardSpark label={kpi3.label} value={kpi3.value} sub={kpi3.sub} />
        <window.KpiCardSpark label="Abrangência geográfica" value={banco?.scope || '—'} sub={banco?.domain || ''} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline={`Ranking · ${data.flowLabel}`}
          title={`Maiores parceiros comerciais · ${spec.label}`}
          action={
            <div className="seg">
              {_PARTNER_METRICS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={'seg-opt ' + (metric === m.id ? 'on' : '')}
                  onClick={() => setMetric(m.id)}
                >
                  <span>{m.label}</span>
                </button>
              ))}
            </div>
          }
        />
        <div className="ptn-list">
          {partners.map((p, i) => (
            <div key={p.name} className="ptn-row">
              <span className="ptn-rank tnum">#{i + 1}</span>
              <span className="ptn-name">{p.name}</span>
              <div className="ptn-bars">
                {metric === 'value' ? (
                  <>
                    <div className="ptn-bar exp" style={{ width: (p.exp / max * 100) + '%' }} title={'Exportação ' + fmtMoney(p.exp)}></div>
                    <div className="ptn-bar imp" style={{ width: (p.imp / max * 100) + '%' }} title={'Importação ' + fmtMoney(p.imp)}></div>
                  </>
                ) : (
                  <div className="ptn-bar exp" style={{ width: (valOf(p) / max * 100) + '%' }} title={fmtMetric(p)}></div>
                )}
              </div>
              <span className="ptn-val tnum">{fmtMetric(p)}</span>
            </div>
          ))}
        </div>
        {metric === 'value' && (
          <div className="ptn-legend">
            <span className="ptn-legend-item"><span className="ptn-legend-dot exp"></span>Exportação</span>
            <span className="ptn-legend-item"><span className="ptn-legend-dot imp"></span>Importação</span>
          </div>
        )}
      </div>
    </>
  );
}

window.ViewPartners = ViewPartners;
