// StackedPanels — Plotly small-multiples: one stacked line panel per series,
// aligned on a shared year axis. Same name + props as the prototype's SVG
// StackedPanels, so the reused views render <window.StackedPanels/> unchanged —
// now with zoom/pan/hover. Handles any number of series and any mix of units.
//   series: [{ label, color, unit, bancoShort, data: [{ y, v }] }]

import { Plot, baseLayout, ptBrLinearAxis, resolveColor, seriesMax, vizPalette, withAlpha, yearAxis } from './_base';

function StackedPanels({ series = [], panelHeight = 150 }) {
  // Guard empty/degenerate input — never throw.
  if (!series.length) {
    return <Plot traces={[]} layout={baseLayout()} height={panelHeight} />;
  }

  const palette = vizPalette();
  const n = series.length;

  // One scatter trace per series, each pinned to its OWN subplot cell — i.e. its
  // own x/y axis pair (x/y, x2/y2, …). Plotly's `grid: pattern:'independent'`
  // requires a matched x AND y axis per row; binding only the y axis (the old
  // bug) left x2…xN undefined → an invalid layout that threw and degraded to the
  // error fallback, so "Painéis" never rendered.
  const traces = series.map((s, si) => {
    const c = resolveColor(s.color, palette[si % palette.length]);
    const data = s.data || [];
    const axisId = si === 0 ? 'y' : `y${si + 1}`;
    const xAxisId = si === 0 ? 'x' : `x${si + 1}`;
    const unit = s.unit ? ` ${s.unit}` : '';
    return {
      x: data.map((d) => d.y),
      y: data.map((d) => d.v),
      type: 'scatter',
      mode: 'lines',
      xaxis: xAxisId,
      yaxis: axisId,
      line: { color: c, width: 2, shape: 'linear' },
      fill: 'tozeroy',
      fillcolor: withAlpha(c, 0.1),
      hovertemplate: `<b>%{x}</b>  %{y:,.2f}${unit}<extra>${s.label || ''}</extra>`,
      name: s.label || '',
    };
  });

  // Per-panel identity goes in a HORIZONTAL title ABOVE each panel (a subplot
  // title), NOT a rotated y-axis title. The long "label · source" string rendered
  // ≈161px tall when rotated — taller than the ≈120px panel — so it overflowed into
  // the neighbouring panel and the vertical texts overlapped. The y axis now keeps
  // only its numeric ticks; the unit travels with the horizontal title instead.
  // pt-BR magnitude ticks ("15 bi" not the SI "15G"), each panel against its OWN
  // series max (FINDING #9). Falls back to `~s` when a panel has no positive max.
  const titleColor = resolveColor('var(--pres-gray-900)', '#333333');
  const yaxes = {};
  const annotations = [];
  series.forEach((s, si) => {
    const axisNum = si === 0 ? '' : String(si + 1);
    const axisKey = si === 0 ? 'yaxis' : `yaxis${si + 1}`;
    yaxes[axisKey] = {
      rangemode: 'tozero',
      ...ptBrLinearAxis(seriesMax(s.data || [], (d) => d.v)),
      automargin: true,
    };
    const idBits = [s.label, s.bancoShort].filter(Boolean).join(' · ');
    annotations.push({
      text: `<b>${idBits}</b>${s.unit ? `  ·  ${s.unit}` : ''}`,
      xref: `x${axisNum} domain`,
      yref: `y${axisNum} domain`,
      x: 0,
      y: 1,
      xanchor: 'left',
      yanchor: 'bottom',
      yshift: 5,
      showarrow: false,
      font: { size: 11, color: titleColor },
      align: 'left',
    });
  });

  // One x axis per row (the grid needs a matched pair per cell). Only the bottom
  // row shows tick labels, so the panels read as a single shared year axis;
  // matches:'x' locks every panel's year range together on zoom/pan.
  const xaxes = {};
  series.forEach((s, si) => {
    const axisKey = si === 0 ? 'xaxis' : `xaxis${si + 1}`;
    xaxes[axisKey] = yearAxis({
      showticklabels: si === n - 1,
      ...(si === 0 ? {} : { matches: 'x' }),
    });
  });

  const layout = baseLayout({
    // ygap opens room BETWEEN stacked panels for each panel's horizontal title;
    // t leaves room for the FIRST panel's title above the top panel.
    grid: { rows: n, columns: 1, pattern: 'independent', roworder: 'top to bottom', ygap: 0.32 },
    margin: { l: 52, r: 16, t: 26, b: 36 },
    annotations,
    ...xaxes,
    ...yaxes,
  });

  return <Plot traces={traces} layout={layout} height={n * panelHeight} />;
}

window.StackedPanels = StackedPanels;
export default StackedPanels;
