// ViewSeasonality — month × year patterns. Generic via the monthlyData
// contract. Synthetic preview until a banco with monthly granularity is live.

function ViewSeasonality({ summary, conventions, database }) {
  const banco = window.bancoById(database);
  const data  = window.monthlyData(database, summary);

  const peakIdx = data.monthlyAvg.indexOf(Math.max(...data.monthlyAvg));
  const lowIdx  = data.monthlyAvg.indexOf(Math.min(...data.monthlyAvg));
  const amplitude = data.monthlyAvg[peakIdx] / (data.monthlyAvg[lowIdx] || 1);
  const fmt = (v) => data.unit + ' ' + v.toLocaleString('pt-BR');

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco}
        capabilityNote="A análise sazonal exige granularidade mensal/diária, ainda não disponível nesta fonte." />}

      <div className="kpi-row">
        <window.KpiCardSpark label="Mês de pico" value={window.MONTH_LABELS[peakIdx]} sub={fmt(data.monthlyAvg[peakIdx]) + ' (média)'} />
        <window.KpiCardSpark label="Mês de vale" value={window.MONTH_LABELS[lowIdx]} sub={fmt(data.monthlyAvg[lowIdx]) + ' (média)'} />
        <window.KpiCardSpark label="Amplitude sazonal" value={'×' + amplitude.toFixed(2).replace('.', ',')} sub="pico ÷ vale" />
        <window.KpiCardSpark label="Cobertura" value={data.years.length + ' anos'} sub={`${data.years[0]}–${data.years[data.years.length - 1]}`} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Mapa de calor · mês × ano"
          title="Padrão sazonal ao longo dos anos"
          action={<span className="caption">{data.unit} · valores ilustrativos</span>}
        />
        <window.MonthYearHeatmap matrix={data.matrix} years={data.years} unit={data.unit} />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Perfil sazonal médio"
          title="Média de cada mês no período"
        />
        <window.BarChart
          data={data.monthlyAvg.map((v, m) => ({ name: window.MONTH_LABELS[m], value: v }))}
          valueKey="value" color="var(--viz-3)" height={300} />
      </div>
    </>
  );
}

window.ViewSeasonality = ViewSeasonality;
