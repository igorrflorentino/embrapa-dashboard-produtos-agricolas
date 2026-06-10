// FlagBars — Plotly 100%-stacked horizontal bars (one bar per product / UF).
// Same name + props as the prototype's SVG FlagBars, so the reused views render
// <window.FlagBars/> unchanged — now with hover/zoom from Plotly. One trace per
// flag; each row carries the flag fractions under flags[].id (values are 0-1).
//   rows:  [{ [labelKey], name, <flagId>: fraction }]
//   flags: [{ id, label, color }]

import { Plot, baseLayout, resolveColor } from './_base';

function FlagBars({ rows = [], flags = [], labelKey = 'code', height }) {
  // Row category labels (y axis). Fall back through the prototype's key order.
  const cats = rows.map((r) => r[labelKey] ?? r.code ?? r.uf ?? r.name ?? '');
  const H = height || Math.max(120, 14 + rows.length * 30 + 14);

  // No rows or no flags selected → empty plot, never crash on flags[0].
  if (rows.length === 0 || flags.length === 0) {
    return <Plot traces={[]} layout={baseLayout()} height={H} />;
  }

  // One horizontal bar trace per flag; values are 0-1 fractions stacked to 100%.
  const traces = flags.map((f) => ({
    type: 'bar',
    orientation: 'h',
    name: f.label,
    y: cats,
    x: rows.map((r) => r[f.id] || 0),
    marker: { color: resolveColor(f.color) },
    hovertemplate: `<b>%{y}</b> · ${f.label}: %{x:.1%}<extra></extra>`,
  }));

  const layout = baseLayout({
    barmode: 'stack',
    barnorm: 'fraction', // guarantees each bar sums to 100% even if rows drift
    hovermode: 'closest',
    showlegend: true,
    legend: { orientation: 'h', y: -0.15, x: 0, font: { size: 11 } },
    margin: { l: 120, r: 16, t: 8, b: 40 },
    xaxis: {
      title: { text: 'Participação', font: { size: 11 }, standoff: 8 },
      tickformat: '.0%',
      range: [0, 1],
    },
    yaxis: { autorange: 'reversed', tickfont: { size: 11 } },
  });

  return <Plot traces={traces} layout={layout} height={H} />;
}

window.FlagBars = FlagBars;
export default FlagBars;
