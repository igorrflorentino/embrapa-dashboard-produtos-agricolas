// ViewSeasonality — month × year patterns. Generic via the monthlyData
// contract. Synthetic preview until a banco with monthly granularity is live.

function ViewSeasonality({ summary, conventions, database }) {
  const banco = window.bancoById(database);
  const data  = window.monthlyData(database, summary);

  // Defensive guards: a real /api/monthly empty frame can ship monthlyAvg: []
  // (or fewer than 12 values). Math.max(...[]) is -Infinity and [].indexOf(...) is
  // -1, so monthlyAvg[-1] = undefined and fmt(undefined).toLocaleString throws —
  // sending the whole perspective to the error boundary instead of an honest
  // empty state. Pad to 12 zeros and clamp the indices so the math always survives.
  const avg = Array.isArray(data.monthlyAvg) && data.monthlyAvg.length === 12
    ? data.monthlyAvg
    : Array.from({ length: 12 }, (_, m) => (data.monthlyAvg && data.monthlyAvg[m]) || 0);
  const years = Array.isArray(data.years) ? data.years : [];
  const hasData = avg.some(v => v > 0);

  const peakIdx = Math.max(0, avg.indexOf(Math.max(...avg)));
  const lowIdx  = Math.max(0, avg.indexOf(Math.min(...avg)));
  const amplitude = avg[peakIdx] / (avg[lowIdx] || 1);
  const fmt = (v) => data.unit + ' ' + (Number(v) || 0).toLocaleString('pt-BR');
  const yearSpan = years.length ? `${years[0]}–${years[years.length - 1]}` : '—';

  if (!hasData) {
    return (
      <>
        {data.preview && <window.PreviewBanner banco={banco}
          capabilityNote="A análise sazonal exige granularidade mensal/diária, ainda não disponível nesta fonte." />}
        <window.NotApplicableNote note={data.notApplicable} />
        <div className="card subtle">
          <window.SectionHeader overline="Mapa de calor · mês × ano" title="Sem dados sazonais para esta seleção" />
          <p className="caption" style={{ padding: '16px 4px' }}>
            Não há série mensal disponível para o banco e os filtros atuais. Ajuste o período ou a
            cesta de produtos, ou selecione um banco com granularidade mensal.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco}
        capabilityNote="A análise sazonal exige granularidade mensal/diária, ainda não disponível nesta fonte." />}

      {/* The seasonality mart collapses the UF away, so an origin-UF filter cannot
          narrow it on any banco — say so honestly above the (unfiltered) charts. */}
      <window.NotApplicableNote note={data.notApplicable} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Mês de pico" value={window.MONTH_LABELS[peakIdx]} sub={fmt(avg[peakIdx]) + ' (média)'} />
        <window.KpiCardSpark label="Mês de vale" value={window.MONTH_LABELS[lowIdx]} sub={fmt(avg[lowIdx]) + ' (média)'} />
        <window.KpiCardSpark label="Amplitude sazonal" value={'×' + amplitude.toFixed(2).replace('.', ',')} sub="pico ÷ vale" />
        <window.KpiCardSpark label="Cobertura" value={years.length + ' anos'} sub={yearSpan} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Mapa de calor · mês × ano"
          title="Padrão sazonal ao longo dos anos"
          action={<span className="caption">{data.unit}{data.preview ? ' · valores ilustrativos' : ''}</span>}
        />
        <window.MonthYearHeatmap matrix={data.matrix} years={years} unit={data.unit} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Perfil sazonal médio"
          title="Média de cada mês no período"
        />
        <window.BarChart
          data={avg.map((v, m) => ({ name: window.MONTH_LABELS[m], value: v }))}
          valueKey="value" color="var(--viz-3)" height={300} />
      </div>
    </>
  );
}

window.ViewSeasonality = ViewSeasonality;
