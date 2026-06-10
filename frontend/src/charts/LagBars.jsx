// LagBars — Plotly signed bar chart for a cross-correlation lag profile. Same
// name + props as the prototype's SVG LagBars, so the reused views render
// <window.LagBars/> unchanged — now with zoom/pan/hover.
//   profile: [{ lag, corr }]  (lag in months, corr in −1…1)
//   best:    { lag, corr }     (the highlighted bar)

import { Plot, baseLayout, resolveColor } from './_base';

function LagBars({ profile = [], best = {}, height = 200 }) {
  // Per-bar color: best lag → embrapa green; otherwise positive vs negative r.
  const green = resolveColor('var(--embrapa-green)', '#2E7D32');
  const pos = resolveColor('var(--viz-4)', '#5B8C5A');
  const neg = resolveColor('var(--err)', '#C0392B');
  const hasBest = best && typeof best.lag === 'number';

  const colors = profile.map((d) =>
    hasBest && d.lag === best.lag ? green : d.corr >= 0 ? pos : neg,
  );
  const opacities = profile.map((d) => (hasBest && d.lag === best.lag ? 1 : 0.7));

  const traces = [
    {
      x: profile.map((d) => d.lag),
      y: profile.map((d) => d.corr),
      type: 'bar',
      marker: { color: colors, opacity: opacities },
      customdata: profile.map((d) => (d.lag >= 0 ? `+${d.lag}` : `${d.lag}`)),
      hovertemplate: 'defasagem %{customdata} m: r = %{y:,.2f}<extra></extra>',
      name: 'correlação (r)',
    },
  ];

  const layout = baseLayout({
    hovermode: 'closest',
    margin: { l: 48, r: 14, t: 18, b: 34 },
    yaxis: {
      title: { text: 'correlação (r)', font: { size: 11 }, standoff: 8 },
      range: [-1, 1],
      zeroline: true,
      tickformat: ',.1f',
    },
    xaxis: {
      title: { text: 'defasagem dos embarques (meses) →', font: { size: 11 }, standoff: 6 },
      dtick: 1,
      tickformat: '+d',
    },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.LagBars = LagBars;
export default LagBars;
