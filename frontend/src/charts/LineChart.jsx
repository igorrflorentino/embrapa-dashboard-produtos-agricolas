// LineChart — Plotly line+area for a single annual series. Same name + props as
// the prototype's SVG LineChart, so the reused views render <window.LineChart/>
// unchanged — but now with zoom/pan/hover (the point of the Plotly migration).
//   data: [{ y, [valueKey] }]

import { Plot, baseLayout, resolveColor, withAlpha } from './_base';

function LineChart({ data = [], height = 200, color = 'var(--viz-1)', label = '', valueKey = 'v' }) {
  const c = resolveColor(color);
  const traces = [
    {
      x: data.map((d) => d.y),
      y: data.map((d) => d[valueKey]),
      type: 'scatter',
      mode: 'lines',
      line: { color: c, width: 2, shape: 'linear' },
      fill: 'tozeroy',
      fillcolor: withAlpha(c, 0.1),
      hovertemplate: '<b>%{x}</b>  %{y:,.2f}<extra></extra>',
      name: label,
    },
  ];
  const layout = baseLayout({
    margin: { l: 56, r: 12, t: 18, b: 28 },
    yaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      tickformat: '~s',
    },
    xaxis: { dtick: 'auto', tickformat: 'd' },
  });
  return <Plot traces={traces} layout={layout} height={height} />;
}

window.LineChart = LineChart;
export default LineChart;
