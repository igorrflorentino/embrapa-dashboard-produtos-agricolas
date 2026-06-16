// MonthYearHeatmap — Plotly heatmap of 12 months (x) × years (y). Same name +
// props as the prototype's SVG version, so the reused views render
// <window.MonthYearHeatmap/> unchanged — now with zoom/pan/hover.
//   matrix: { [year]: number[12] }

import { Plot, baseLayout, cssVar, resolveColor } from './_base';

// Default month labels if the global isn't set (matches the prototype's pt-BR).
const FALLBACK_MONTHS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function MonthYearHeatmap({ matrix = {}, years = [], unit = '', height, formatValue = null }) {
  const months = (typeof window !== 'undefined' && window.MONTH_LABELS) || FALLBACK_MONTHS;
  // Rows sorted descending so the most recent year sits at the top (as the SVG).
  const rows = years.slice().sort((a, b) => b - a);

  // Guard empty/degenerate input — render an empty Plot rather than throwing.
  if (!rows.length) {
    return <Plot traces={[]} layout={baseLayout()} height={height || 240} />;
  }

  // z[yearIdx] = matrix[year] (one row of 12 monthly values per year).
  const z = rows.map((y) => matrix[y] || []);

  // Per-cell hover text via a caller-supplied formatter so the magnitude shows:
  // the serializer pre-scales monthly values to millions, so the raw "%{z}" with a
  // bare unit would read e.g. 2.07 instead of "2,07 mi US$". Default = value+unit.
  const fmtVal = formatValue || ((v) =>
    `${(Number(v) || 0).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ''}`);
  const customdata = z.map((row) => row.map(fmtVal));

  // Heat ramp from the design-system --heat-1…--heat-7 stops, resolved for Plotly.
  const stops = Array.from({ length: 7 }, (_, i) => resolveColor(`var(--heat-${i + 1})`));
  const colorscale = stops.map((c, i) => [i / (stops.length - 1), c]);

  const traces = [
    {
      type: 'heatmap',
      x: months,
      y: rows,
      z,
      colorscale,
      customdata,
      showscale: true,
      colorbar: { title: { text: unit, side: 'right', font: { size: 11 } }, thickness: 12 },
      hovertemplate: '%{x}/%{y}: %{customdata}<extra></extra>',
      xgap: 1,
      ygap: 3,
    },
  ];

  const layout = baseLayout({
    margin: { l: 56, r: 56, t: 24, b: 28 },
    hovermode: 'closest',
    xaxis: { side: 'top', type: 'category', fixedrange: true },
    yaxis: {
      title: { text: 'Ano', font: { size: 11 }, standoff: 8 },
      type: 'category',
      autorange: 'reversed', // keep descending order top→bottom (rows already sorted desc)
      gridcolor: cssVar('--pres-gray-200', '#ECECEC'),
    },
  });

  return <Plot traces={traces} layout={layout} height={height || 240} />;
}

window.MonthYearHeatmap = MonthYearHeatmap;
export default MonthYearHeatmap;
