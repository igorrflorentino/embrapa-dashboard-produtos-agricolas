// MultiLineChart — Plotly multi-series lines on one shared axis (comparison
// views). Same name + props as the prototype's SVG MultiLineChart, so the
// reused views render <window.MultiLineChart/> unchanged — now with zoom/pan/
// hover and a per-series legend (the point of the Plotly migration).
//   series: [{ name, color, data: [{ y, [valueKey] }] }]

import { Plot, baseLayout, resolveColor, vizPalette } from './_base';

function MultiLineChart({ series = [], valueKey = 'v', label = '', height = 200 }) {
  const palette = vizPalette();
  // One scatter line per series; fall back to the categorical palette when a
  // series omits its color so concurrent lines stay visually distinct.
  const traces = series.map((s, i) => ({
    x: (s.data || []).map((d) => d.y),
    y: (s.data || []).map((d) => d[valueKey]),
    type: 'scatter',
    mode: 'lines',
    line: { color: resolveColor(s.color, palette[i % palette.length]), width: 2, shape: 'linear' },
    name: s.name,
    hovertemplate: '<b>%{x}</b>  %{y:,.2f}<extra>%{fullData.name}</extra>',
  }));

  const layout = baseLayout({
    margin: { l: 56, r: 12, t: 18, b: 28 },
    showlegend: true,
    legend: { orientation: 'h', y: 1.12, x: 0, font: { size: 11 } },
    yaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      tickformat: '~s',
    },
    xaxis: { dtick: 'auto', tickformat: 'd' },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.MultiLineChart = MultiLineChart;
export default MultiLineChart;
