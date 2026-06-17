// YoYBars — Plotly signed bars for year-over-year % variation. Same name + props
// as the prototype's SVG YoYBars, so the reused views render <window.YoYBars/>
// unchanged — but now with zoom/pan/hover (the point of the Plotly migration).
//   data: [{ y, [valueKey] }]

import { Plot, baseLayout, resolveColor, cssVar } from './_base';

function YoYBars({ data = [], valueKey = 'v', height = 200 }) {
  // Empty/degenerate input → empty plot, never throw.
  if (!data || data.length === 0) {
    return <Plot traces={[]} layout={baseLayout()} height={height} />;
  }

  // YoY % change: ((v[i]-v[i-1])/v[i-1])*100. First point, a missing prev
  // (null/undefined), or prev===0 → 0% rather than a divide-by-zero
  // NaN/Infinity. A null/zero-aware guard (not `!prev`) so a legit negative or
  // small fractional prev still yields a real YoY instead of being zeroed.
  const yoy = data.map((d, i) => {
    const prev = i === 0 ? null : data[i - 1][valueKey];
    const noBase = prev == null || prev === 0;
    return { y: d.y, pct: noBase ? 0 : ((d[valueKey] - prev) / prev) * 100 };
  });

  // Skip the first point (no prior year to compare against), matching the design system.
  const bars = yoy.slice(1);

  const ok = resolveColor('var(--ok)');
  const err = resolveColor('var(--err)');

  const traces = [
    {
      x: bars.map((d) => d.y),
      y: bars.map((d) => d.pct),
      type: 'bar',
      marker: { color: bars.map((d) => (d.pct >= 0 ? ok : err)), opacity: 0.85 },
      hovertemplate: '<b>%{x}</b>  %{y:+,.2f}%<extra></extra>',
      name: 'Variação anual',
    },
  ];

  const layout = baseLayout({
    margin: { l: 56, r: 12, t: 18, b: 28 },
    yaxis: {
      title: { text: 'Variação anual (%)', font: { size: 11 }, standoff: 8 },
      ticksuffix: '%',
      zeroline: true,
      zerolinecolor: cssVar('--pres-gray-200', '#ECECEC'),
    },
    xaxis: { dtick: 'auto', tickformat: 'd' },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.YoYBars = YoYBars;
export default YoYBars;
