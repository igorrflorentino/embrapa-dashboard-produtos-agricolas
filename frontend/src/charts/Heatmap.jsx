// Heatmap — Plotly year (x) × category (y) color matrix. Same name + props as
// the prototype's SVG Heatmap, so the reused views render <window.Heatmap/>
// unchanged — now with zoom/pan/hover (the point of the Plotly migration).
//   rows: [{ id, label, values: [{ y, v }] }]

import { Plot, baseLayout, resolveColor } from './_base';

// The design-system heat ramp (--heat-1…--heat-7), resolved to concrete colors
// and mapped onto a Plotly colorscale (normalized stops 0→1).
function heatColorscale() {
  const stops = Array.from({ length: 7 }, (_, i) =>
    resolveColor(`var(--heat-${i + 1})`, '#1D4D7E'),
  );
  return stops.map((c, i) => [i / (stops.length - 1), c]);
}

function Heatmap({ rows = [], valueKey = 'v', valueLabel = '', height }) {
  // No rows (e.g. all UFs filtered out) or an empty first row → empty plot,
  // never touch rows[0].values.
  if (!rows.length || !rows[0].values?.length) {
    return <Plot traces={[]} layout={baseLayout()} height={height || 120} />;
  }

  // x = years (aligned across rows by the first row), y = row labels,
  // z = a matrix of values aligned by year.
  const x = rows[0].values.map((d) => d.y);
  const y = rows.map((r) => r.label);
  const z = rows.map((r) => r.values.map((d) => d[valueKey] ?? null));

  const traces = [
    {
      type: 'heatmap',
      x,
      y,
      z,
      colorscale: heatColorscale(),
      showscale: true,
      colorbar: { title: { text: valueLabel, side: 'right', font: { size: 11 } }, thickness: 12 },
      hovertemplate: `<b>%{y}</b> · %{x}<br>%{z:,.2f} ${valueLabel}<extra></extra>`,
    },
  ];

  const layout = baseLayout({
    margin: { l: 120, r: 16, t: 8, b: 36 },
    hovermode: 'closest',
    // x = year categories (top-to-bottom row order preserved via reversed y).
    xaxis: { type: 'category', tickangle: 0 },
    yaxis: { type: 'category', autorange: 'reversed', automargin: true },
  });

  // Fall back to a row-count-aware height when none is supplied.
  return <Plot traces={traces} layout={layout} height={height || 22 + rows.length * 24 + 22} />;
}

window.Heatmap = Heatmap;
export default Heatmap;
