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

  // Partial-latest-year guard (FINDING #3). A monthly banco (COMEX) publishes the
  // current year month-by-month, so its latest year in `ts` covers only a few
  // months — anchoring the headline KPI + YoY there reads a partial year vs a
  // full year as a spurious crash (the live audit caught COMEX "−41,2% 2026 vs
  // 2025"). The backend flags completeness on /api/source-meta; when the latest
  // year is partial we anchor the headline value + YoY on the latest COMPLETE
  // year and surface the partial year only in the time-series chart, marked
  // "(parcial)". Annual bancos (PEVS/PAM/COMTRADE) report complete → unchanged.
  const meta        = (window.dataStore && window.dataStore.meta)
    ? window.dataStore.meta(database) : null;
  const latestMeta  = (meta && meta.latest) || null;
  const lastPoint   = ts[ts.length - 1] || { v: 0, q_mass: 0, q_vol: 0, y: null };
  // The visible latest year is partial only when the backend says so AND that
  // year is actually present at the end of the (possibly filtered) window.
  const partialLatest =
    !!latestMeta &&
    latestMeta.yearComplete === false &&
    lastPoint.y != null &&
    (latestMeta.completeYear == null || lastPoint.y > latestMeta.completeYear) &&
    ts.length >= 2;
  // KPI/YoY anchor: drop the partial trailing year so headline figures compare
  // full-year vs full-year. The chart below still renders the full `ts`.
  const tsKpi     = partialLatest ? ts.slice(0, -1) : ts;
  const partialYr = partialLatest ? lastPoint.y : null;
  const last      = tsKpi[tsKpi.length - 1] || { v: 0, q_mass: 0, q_vol: 0 };
  const prev      = tsKpi[tsKpi.length - 2] || last;
  const first     = ts[0] || last;
  const deltaV    = prev.v ? ((last.v - prev.v) / prev.v) * 100 : 0;
  const deltaTotV = first.v ? ((last.v - first.v) / first.v) * 100 : 0;
  const spark12   = ts.slice(-12);

  // Quality digest from filtered flag set
  const okFlag    = filtered.qualityFlags.find(f => f.id === 'OK');
  const okShare   = okFlag ? okFlag.share : 0;
  const okCount   = okFlag ? okFlag.count : 0;

  // "UFs cobertas" must count REAL Brazilian states only. For a trade banco
  // (COMEX) ufData includes non-state pseudo-origins (ND/EX/ZN/CB/RE/MC…) that
  // are not UFs, so counting every row with value>0 yielded a nonsensical 32/27.
  // The backend now flags each row `real` (true = Brazilian UF); we count those.
  // Fallback (older payloads / synthetic data lacking `real`): intersect with the
  // canonical 27-UF registry (window.UF_DATA) so pseudo-codes never inflate it.
  const isRealUf  = u => (u.real != null ? u.real : window.isCanonicalUf(u.uf));
  const realUfs   = filtered.ufData.filter(isRealUf);
  const ufCovered = realUfs.filter(u => u.value > 0).length;
  // Denominator = real UFs in the banco's full set, capped at the canonical 27.
  const ufTotalReal = Math.min(
    27,
    filtered.ufDataFull.filter(isRealUf).length || 27,
  );
  const top3      = realUfs.slice().sort((a, b) => b.value - a.value).slice(0, 3);
  const hasGeo    = filtered.ufDataFull.length > 0;
  // The tile map is scoped to the latest UF year IN the window, which can fall short
  // of yearEnd (future/partial endDate). Label it with the data's OWN year so the
  // caption never diverges from what's plotted (FINDING #1).
  const mapYear    = filtered.ufLatestYear != null ? filtered.ufLatestYear : filtered.yearEnd;
  // Mark "(parcial)" when EITHER the UF data lags the window end (ufYearPartial)
  // OR the map year is the calendar-partial latest year (FINDING #3 signal), so
  // the spatial snapshot is as honest as the time-series point.
  const mapPartial = filtered.ufYearPartial || (partialLatest && mapYear === partialYr);
  const mapYearTag = mapPartial ? `${mapYear} (parcial)` : `${mapYear}`;
  // The composition donut shows the latest year (yearEnd); mark it partial too when
  // that trailing year is incomplete, consistent with the map + series.
  const compYearTag = (partialLatest && filtered.yearEnd === partialYr)
    ? `${filtered.yearEnd} (parcial)`
    : `${filtered.yearEnd}`;

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
                {partialLatest && (
                  <p className="caption" style={{ padding: '8px 4px 0' }}>
                    <strong>{partialYr} (parcial):</strong> o ano mais recente cobre apenas
                    {' '}{latestMeta?.monthsInLatestYear ? `${latestMeta.monthsInLatestYear} ${latestMeta.monthsInLatestYear === 1 ? 'mês' : 'meses'}` : 'parte do ano'}.
                    Os indicadores e a variação anual acima usam o último ano <strong>completo</strong> ({last.y});
                    o ponto parcial aparece apenas na série.
                  </p>
                )}
              </>
            );
          })()}
        </div>

        <div className="card">
          <window.SectionHeader
            overline={`Composição · ${compYearTag}`}
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
            // Only REAL UFs reach the tile map: a trade banco's ufData carries
            // non-state pseudo-origins (ND/EX/ZN…) with no tile col/row, which the
            // BrazilTileMap would position at `undefined * cell = NaN` (FINDING #4/#5).
            const ufRows = realUfs.map(u => ({
              ...u,
              value: u.value * 1e6 * ufFactor,
            }));
            const max = Math.max(...ufRows.map(u => u.value), 0);
            const { data, label } = window.scaleSeries(ufRows, max, conv, 'value', valAxis);
            return (
              <>
                <window.SectionHeader
                  overline={`Distribuição geográfica · ${mapYearTag}`}
                  title={`Valor por UF · ${label}`}
                  action={
                    <span className="caption">
                      {top3.length ? 'Top 3: ' + top3.map(u => u.uf).join(' · ') : '—'}
                    </span>
                  }
                />
                <window.BrazilTileMap data={data} valueKey="value" label={label} />
                {filtered.ufYearPartial && (
                  <p className="caption" style={{ padding: '8px 4px 0' }}>
                    <strong>{mapYear} (parcial):</strong> o último ano com dados por UF fica antes do
                    fim do período ({filtered.yearEnd}); o mapa mostra {mapYear}.
                  </p>
                )}
                {filtered.notFilteredByBasket && (
                  <p className="caption" style={{ padding: '8px 4px 0' }}>
                    O mapa reflete <strong>todos os produtos</strong> — a cesta selecionada não
                    recorta a distribuição por UF (sem grão produto × UF nesta agregação).
                  </p>
                )}
              </>
            );
          })()}
        </div>
        )}

        <div className="card">
          <window.SectionHeader
            overline="Qualidade dos dados · agregado"
            title={hasGeo
              ? ('Cobertura geográfica: ' + ufCovered + ' / ' + ufTotalReal + ' UFs')
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
