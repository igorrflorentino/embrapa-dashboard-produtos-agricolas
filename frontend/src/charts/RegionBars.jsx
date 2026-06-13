// RegionBars — Plotly vertical bars for region totals. Same name + props as the
// prototype's SVG RegionBars, so the reused views render <window.RegionBars/>
// unchanged — but now with zoom/pan/hover (the point of the Plotly migration).
//   data: [{ id, label, color, [valueKey], ufs }]

import { Plot, baseLayout, ptBrLinearAxis, resolveColor, seriesMax, vizPalette } from './_base';

function RegionBars({ data = [], valueKey = 'value', label = '', height = 200 }) {
  // One bar per region, colored by d.color (falling back to the categorical
  // viz palette when a region carries no explicit color). Empty input → empty
  // plot area, never crash on an empty data array.
  const palette = vizPalette();
  const colors = data.map((d, i) => resolveColor(d.color, palette[i % palette.length]));

  const traces = [
    {
      x: data.map((d) => d.label),
      y: data.map((d) => d[valueKey]),
      type: 'bar',
      marker: { color: colors },
      // ufs rides along as customdata so the hover can show the UF count.
      customdata: data.map((d) => d.ufs),
      hovertemplate: '<b>%{x}</b>  %{y:,.2f}<br>%{customdata} UF<extra></extra>',
      name: label,
    },
  ];

  const layout = baseLayout({
    margin: { l: 56, r: 12, t: 18, b: 38 },
    yaxis: {
      title: { text: label, font: { size: 11 }, standoff: 8 },
      rangemode: 'tozero',
      // pt-BR magnitude ticks ("15 bi" not the SI "15G"), consistent across cards
      // (FINDING #9). Falls back to `~s` when there is no usable positive max.
      ...ptBrLinearAxis(seriesMax(data, (d) => d[valueKey])),
    },
    xaxis: { type: 'category' },
  });

  return <Plot traces={traces} layout={layout} height={height} />;
}

window.RegionBars = RegionBars;
export default RegionBars;
