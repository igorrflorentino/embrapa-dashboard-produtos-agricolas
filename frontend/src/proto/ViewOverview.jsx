// ViewOverview — a digest of the other three perspectives.
// All datasets pass through window.applyFilters(summary) so KPIs,
// charts and the donut only reflect the rows the researcher selected.

function ViewOverview({ families, summary, database, conventions }) {
  const conv      = conventions || window.DEFAULT_CONVENTIONS;
  const monLabel  = window.conventionMonetaryLabel(conv);
  const valAxis   = window.valueAxisLabel(conv);
  // ufData is in the banco's OWN base currency (USD for COMEX/Comtrade), so scale
  // it with the base-aware factor — convFactor alone leaves a US$ magnitude under
  // R$ when a USD-native banco switches display to BRL. base=BRL → unchanged.
  const baseCcy   = window.canonCurrencyFor ? window.canonCurrencyFor(database) : 'BRL';
  const ufFactor  = window.convFactorFor(baseCcy, conv);

  const filtered = window.applyFilters(summary || {}, database);

  // ts.v is in R$ bi; scale to absolute.
  const ts        = filtered.ts.map(d => ({ ...d, v: d.v * 1e9 }));
  const last      = ts[ts.length - 1] || { v: 0, q_mass: 0, q_vol: 0 };
  const prev      = ts[ts.length - 2] || last;
  const first     = ts[0] || last;
  const deltaV    = prev.v ? ((last.v - prev.v) / prev.v) * 100 : 0;
  const deltaTotV = first.v ? ((last.v - first.v) / first.v) * 100 : 0;
  const spark12   = ts.slice(-12);

  // Quality digest from filtered flag set
  const okFlag    = filtered.qualityFlags.find(f => f.id === 'OK');
  const okShare   = okFlag ? okFlag.share : 0;
  const okCount   = okFlag ? okFlag.count : 0;

  const ufCovered = filtered.ufData.filter(u => u.value > 0).length;
  const top3      = filtered.ufData.slice().sort((a, b) => b.value - a.value).slice(0, 3);
  const hasGeo    = filtered.ufDataFull.length > 0;

  const massFamily = families.includes('mass');
  const volFamily  = families.includes('volume');

  return (
    <>
      <window.UnitFamilyBanner families={families} />

      {/* KPI strip */}
      <div className="kpi-row">
        <window.KpiCardSpark
          label={`Valor total · ${monLabel}`}
          value={window.formatValue(last.v, conv)}
          delta={window.fmtSigned(deltaV)}
          deltaPositive={deltaV >= 0}
          sub={`${last.y || ''} vs. ${prev.y || ''}`}
          spark={window.convertSeries(spark12, conv)}
          sparkKey="v"
          sparkColor="var(--viz-1)"
        />
        {massFamily && (
          <window.KpiCardSpark
            label={<>Quantidade · <window.UnitFamilyTag family="mass" conv={conv}/></>}
            value={window.formatMassQty(last.q_mass, conv)}
            delta={window.fmtSigned(prev.q_mass ? ((last.q_mass - prev.q_mass) / prev.q_mass) * 100 : 0)}
            deltaPositive={last.q_mass >= prev.q_mass}
            sub={`${last.y || ''} vs. ${prev.y || ''}`}
            spark={spark12}
            sparkKey="q_mass"
            sparkColor="var(--viz-2)"
          />
        )}
        {volFamily && (
          <window.KpiCardSpark
            label={<>Quantidade · <window.UnitFamilyTag family="volume" conv={conv}/></>}
            value={window.formatVolumeQty(last.q_vol, conv)}
            delta={window.fmtSigned(prev.q_vol ? ((last.q_vol - prev.q_vol) / prev.q_vol) * 100 : 0)}
            deltaPositive={last.q_vol >= prev.q_vol}
            sub={`${last.y || ''} vs. ${prev.y || ''}`}
            spark={spark12}
            sparkKey="q_vol"
            sparkColor="var(--viz-4)"
          />
        )}
        <window.KpiCardSpark
          label="Linhas íntegras (flag = OK)"
          value={window.fmtPct(okShare)}
          sub={okCount ? (okCount / 1e6).toFixed(1).replace('.', ',') + ' mi linhas' : 'OK não selecionada'}
          spark={filtered.qualityTs.slice(-12)}
          sparkKey="ok"
          sparkColor="var(--ok)"
        />
      </div>

      {/* Hero: timeseries + composition */}
      <div className="grid-2">
        <div className="card">
          {(() => {
            const series = window.convertSeries(ts, conv);
            const max = Math.max(...series.map(d => d.v), 0);
            const { data, label } = window.scaleSeries(series, max, conv, 'v', valAxis);
            return (
              <>
                <window.SectionHeader
                  overline={`Série histórica · ${filtered.yearStart}–${filtered.yearEnd} · ${monLabel}`}
                  title={'Variação acumulada: ' + window.fmtSigned(deltaTotV, 0)}
                />
                <window.LineChart data={data} label={label} valueKey="v" color="var(--viz-1)" height={240} />
              </>
            );
          })()}
        </div>

        <div className="card">
          <window.SectionHeader
            overline={`Composição · ${filtered.yearEnd}`}
            title="Participação por produto"
            action={<span className="caption">{filtered.selectedProducts.length} de {filtered.productsTotal} produtos</span>}
          />
          {filtered.topProducts.length === 0 ? (
            <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
              Nenhum produto selecionado nos filtros.
            </p>
          ) : (
            <window.Donut data={filtered.topProducts} size={180} valueKey="share" />
          )}
        </div>
      </div>

      {/* Geo digest + quality digest */}
      <div className="grid-2">
        {hasGeo && (
        <div className="card">
          {(() => {
            const ufRows = filtered.ufData.map(u => ({
              ...u,
              value: u.value * 1e6 * ufFactor,
            }));
            const max = Math.max(...ufRows.map(u => u.value), 0);
            const { data, label } = window.scaleSeries(ufRows, max, conv, 'value', valAxis);
            return (
              <>
                <window.SectionHeader
                  overline={`Distribuição geográfica · ${filtered.yearEnd}`}
                  title={`Valor por UF · ${label}`}
                  action={
                    <span className="caption">
                      {top3.length ? 'Top 3: ' + top3.map(u => u.uf).join(' · ') : '—'}
                    </span>
                  }
                />
                <window.BrazilTileMap data={data} valueKey="value" label={label} />
              </>
            );
          })()}
        </div>
        )}

        <div className="card">
          <window.SectionHeader
            overline="Qualidade dos dados · agregado"
            title={hasGeo
              ? ('Cobertura geográfica: ' + ufCovered + ' / ' + (filtered.ufDataFull.length || 0) + ' UFs')
              : 'Distribuição de flags de qualidade'}
            action={<span className="caption">{filtered.qualityFlags.length} de {window.QUALITY_FLAGS.length} flags</span>}
          />
          <div className="qa-summary">
            {filtered.qualityFlags.map(f => (
              <div key={f.id} className="qa-row">
                <span className="qa-dot" style={{ background: f.color }}></span>
                <span className="qa-label">{f.label}</span>
                <span className="qa-count tnum">{(f.count / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}k</span>
                <span className="qa-share tnum">{window.fmtPct(f.share)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

window.ViewOverview = ViewOverview;
