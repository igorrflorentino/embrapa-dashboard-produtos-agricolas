// MonthlyOverlay — Plotly port of the prototype's SVG MonthlyOverlay. Same name
// + props, so the reused views render <window.MonthlyOverlay/> unchanged — now
// with zoom/pan/hover. Two 12-month line profiles share one month-labelled x;
// markers draw dashed vertical guides at a month index (e.g. harvest/ship peaks).
//   series  : [{ name, color, data: number[12] }]
//   months  : string[12]
//   markers : [{ month, color }]

import { Plot, baseLayout, resolveColor, vizPalette } from './_base';

function MonthlyOverlay({ series = [], months = [], markers = [], label = '' }) {
  const palette = vizPalette();

  // One scatter line per profile. data is a raw number[12]; x is the month label
  // (falls back to the index when months are missing).
  const traces = series.map((s, si) => {
    const c = resolveColor(s.color, palette[si % palette.length]);
    return {
      x: (s.data || []).map((_, i) => months[i] ?? i),
      y: s.data || [],
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: c, width: 2.4, shape: 'linear' },
      marker: { color: c, size: 5 },
      hovertemplate: '<b>%{x}</b>  %{y:,.2f}<extra>' + (s.name || '') + '</extra>',
      name: s.name || '',
    };
  });

  // Peak markers — dashed vertical guides at a month index, drawn as layout shapes
  // so they span the full plot height regardless of the data range.
  const shapes = markers.map((mk) => ({
    type: 'line',
    xref: 'x',
    yref: 'paper',
    x0: months[mk.month] ?? mk.month,
    x1: months[mk.month] ?? mk.month,
    y0: 0,
    y1: 1,
    line: { color: resolveColor(mk.color), width: 1.4, dash: 'dash' },
    opacity: 0.6,
    layer: 'below',
  }));

  const layout = baseLayout({
    margin: { l: 48, r: 14, t: 16, b: 28 },
    hovermode: 'x unified',
    shapes,
    xaxis: { type: 'category', fixedrange: false },
    yaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      tickformat: '~s',
    },
  });

  return <Plot traces={traces} layout={layout} height={280} />;
}

window.MonthlyOverlay = MonthlyOverlay;
export default MonthlyOverlay;
