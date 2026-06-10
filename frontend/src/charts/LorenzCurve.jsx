// LorenzCurve — Plotly concentration/Lorenz curve. Same name + props as the
// prototype's SVG LorenzCurve, so the reused views render <window.LorenzCurve/>
// unchanged — but now with zoom/pan/hover (the point of the Plotly migration).
//   values: number[]  (e.g. per-UF or per-product value)
// Sorts ascending, plots cumulative-share-of-units (x) vs cumulative-share-of-
// value (y), with the 45° line of equality as a dashed reference.

import { Plot, baseLayout, resolveColor, withAlpha } from './_base';

function LorenzCurve({ values = [], color = 'var(--viz-1)', xLabel = '', yLabel = '', height = 200 }) {
  const c = resolveColor(color);
  const equality = resolveColor('var(--fg-3)', '#9AA0A6');

  // Keep only positive values, sorted ascending (matches the prototype).
  const sorted = (values || []).slice().filter((v) => v > 0).sort((a, b) => a - b);
  const n = sorted.length;
  const total = sorted.reduce((s, v) => s + v, 0) || 1;

  // Cumulative share points (0,0) … (1,1).
  const xs = [0];
  const ys = [0];
  let acc = 0;
  sorted.forEach((v, i) => {
    acc += v;
    xs.push((i + 1) / n);
    ys.push(acc / total);
  });

  // 45° line of equality — drawn even on empty input so the frame reads as a chart.
  const traces = [
    {
      x: [0, 1],
      y: [0, 1],
      type: 'scatter',
      mode: 'lines',
      line: { color: equality, width: 1.2, dash: 'dash' },
      opacity: 0.6,
      hoverinfo: 'skip',
      name: 'Igualdade',
    },
  ];

  // Lorenz curve + shaded area (only when we have data).
  if (n > 0) {
    traces.push({
      x: xs,
      y: ys,
      type: 'scatter',
      mode: 'lines',
      line: { color: c, width: 2.2, shape: 'linear' },
      fill: 'tozeroy',
      fillcolor: withAlpha(c, 0.12),
      hovertemplate: `${xLabel || '% acum.'}: %{x:.0%}<br>${yLabel || 'valor'} acum.: %{y:.0%}<extra></extra>`,
      name: yLabel || 'Curva de Lorenz',
    });
  }

  const layout = baseLayout({
    margin: { l: 48, r: 16, t: 16, b: 36 },
    hovermode: 'closest',
    xaxis: {
      title: { text: xLabel ? `${xLabel} acum.` : '% acum.', font: { size: 11 }, standoff: 8 },
      range: [0, 1],
      tickformat: '.0%',
    },
    yaxis: {
      title: { text: yLabel ? `${yLabel} acum.` : '% acum.', font: { size: 11 }, standoff: 8 },
      range: [0, 1],
      tickformat: '.0%',
    },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.LorenzCurve = LorenzCurve;
export default LorenzCurve;
