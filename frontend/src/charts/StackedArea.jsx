// StackedArea — Plotly stacked areas (products as layers over time). Same name +
// props as the prototype's SVG StackedArea, so the reused views render
// <window.StackedArea/> unchanged — now with zoom/pan/hover + a name legend.
//   series: [{ code?, name, color, data: [{ y, [valueKey] }] }]

import { Plot, baseLayout, ptBrLinearAxis, resolveColor, vizPalette } from './_base';

function StackedArea({ series = [], valueKey = 'v', label = '', height = 200 }) {
  const palette = vizPalette();
  // One scatter trace per series, all sharing a stackgroup → Plotly stacks them.
  const traces = (series || []).map((sr, i) => {
    const color = resolveColor(sr.color || palette[i % palette.length]);
    return {
      x: (sr.data || []).map((d) => d.y),
      y: (sr.data || []).map((d) => d[valueKey]),
      type: 'scatter',
      mode: 'lines',
      stackgroup: 'one',
      line: { color, width: 1, shape: 'linear' },
      fillcolor: color,
      name: sr.name || sr.code || `Série ${i + 1}`,
      hovertemplate: '<b>%{fullData.name}</b>  %{y:,.2f}<extra></extra>',
    };
  });

  // pt-BR magnitude ticks ("15 bi" not the SI "15G"), consistent across cards
  // (FINDING #9). The axis is STACKED, so its max is the per-year SUM across series
  // (not any single series' peak). Falls back to `~s` when there is no usable max.
  const stackTotals = {};
  (series || []).forEach((sr) => {
    (sr.data || []).forEach((d) => {
      const v = Number(d[valueKey]);
      if (Number.isFinite(v)) stackTotals[d.y] = (stackTotals[d.y] || 0) + v;
    });
  });
  const ymax = Math.max(0, ...Object.values(stackTotals));
  const layout = baseLayout({
    showlegend: true,
    legend: { orientation: 'h', y: -0.18, x: 0, font: { size: 11 } },
    margin: { l: 56, r: 12, t: 18, b: 44 },
    yaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      ...ptBrLinearAxis(ymax),
    },
    xaxis: { dtick: 'auto', tickformat: 'd' },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.StackedArea = StackedArea;
export default StackedArea;
