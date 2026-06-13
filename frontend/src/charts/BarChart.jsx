// BarChart — Plotly horizontal bars, one per row. Same name + props as the
// prototype's SVG BarChart, so the reused views render <window.BarChart/>
// unchanged — but now with zoom/pan/hover (the point of the Plotly migration).
//   data: [{ uf|name, [valueKey] }]  ·  labeled by d.uf||d.name, value at bar tip.

import { Plot, baseLayout, ptBrLinearAxis, resolveColor, seriesMax } from './_base';

function BarChart({ data = [], height = 200, color = 'var(--viz-2)', label = '', valueKey = 'value' }) {
  const c = resolveColor(color);
  // Category label per row (uf preferred, name fallback) and its value.
  const cats = data.map((d) => d.uf || d.name);
  const vals = data.map((d) => d[valueKey]);

  const traces = [
    {
      x: vals,
      y: cats,
      type: 'bar',
      orientation: 'h',
      marker: { color: c },
      // Value shown at the bar tip (pt-BR thousands, like the prototype).
      text: vals.map((v) => (v == null ? '' : v.toLocaleString('pt-BR'))),
      textposition: 'outside',
      cliponaxis: false,
      hovertemplate: '<b>%{y}</b>  %{x:,.2f}<extra></extra>',
      name: label,
    },
  ];

  const layout = baseLayout({
    hovermode: 'closest',
    margin: { l: 60, r: 24, t: 14, b: 26 },
    xaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      // pt-BR magnitude ticks ("15 bi" not the SI "15G"), consistent across cards
      // (FINDING #9). Falls back to `~s` when there is no usable positive max.
      ...ptBrLinearAxis(seriesMax(vals)),
    },
    // Keep the rows in the order given (first row on top, like the SVG).
    yaxis: { autorange: 'reversed', automargin: true },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.BarChart = BarChart;
export default BarChart;
