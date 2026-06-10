// StackedPanels — Plotly small-multiples: one stacked line panel per series,
// aligned on a shared year axis. Same name + props as the prototype's SVG
// StackedPanels, so the reused views render <window.StackedPanels/> unchanged —
// now with zoom/pan/hover. Handles any number of series and any mix of units.
//   series: [{ label, color, unit, bancoShort, data: [{ y, v }] }]

import { Plot, baseLayout, resolveColor, vizPalette, withAlpha } from './_base';

function StackedPanels({ series = [], panelHeight = 120 }) {
  // Guard empty/degenerate input — never throw.
  if (!series.length) {
    return <Plot traces={[]} layout={baseLayout()} height={panelHeight} />;
  }

  const palette = vizPalette();
  const n = series.length;

  // One scatter trace per series, each pinned to its own y axis (y, y2, …).
  // A shared x axis stacks them via Plotly's subplot grid.
  const traces = series.map((s, si) => {
    const c = resolveColor(s.color, palette[si % palette.length]);
    const data = s.data || [];
    const axisId = si === 0 ? 'y' : `y${si + 1}`;
    const unit = s.unit ? ` ${s.unit}` : '';
    return {
      x: data.map((d) => d.y),
      y: data.map((d) => d.v),
      type: 'scatter',
      mode: 'lines',
      yaxis: axisId,
      line: { color: c, width: 2, shape: 'linear' },
      fill: 'tozeroy',
      fillcolor: withAlpha(c, 0.1),
      hovertemplate: `<b>%{x}</b>  %{y:,.2f}${unit}<extra>${s.label || ''}</extra>`,
      name: s.label || '',
    };
  });

  // Per-panel y axis: compact title carries the series label + source short.
  const yaxes = {};
  series.forEach((s, si) => {
    const axisKey = si === 0 ? 'yaxis' : `yaxis${si + 1}`;
    const titleBits = [s.label, s.bancoShort].filter(Boolean).join(' · ');
    yaxes[axisKey] = {
      title: { text: titleBits, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      tickformat: '~s',
      automargin: true,
    };
  });

  const layout = baseLayout({
    grid: { rows: n, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
    margin: { l: 64, r: 16, t: 8, b: 36 },
    xaxis: { tickformat: 'd', dtick: 'auto' },
    ...yaxes,
  });

  return <Plot traces={traces} layout={layout} height={n * panelHeight} />;
}

window.StackedPanels = StackedPanels;
export default StackedPanels;
