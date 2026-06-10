// BrazilTileMap — choropleth on a 9-row UF tile grid. Kept as SVG: a bespoke
// geographic tile layout with per-cell labels + a heat-bucket scale that Plotly
// can't match and that doesn't benefit from zoom/pan. Faithful port of the
// prototype's component. Same name + props (incl. onSelect for drill-down).
//   data: [{ uf, col, row, region, [valueKey] }]  (col/row decorated client-side)

function BrazilTileMap({ data = [], valueKey = 'value', label = 'R$ mi', height = 420, onSelect }) {
  const COLS = 8;
  const ROWS = 9;
  const CELL_W = 60;
  const CELL_H = 56;
  const GAP = 4;
  const W = COLS * (CELL_W + GAP);
  const H = ROWS * (CELL_H + GAP);

  const vals = data.map((d) => d[valueKey] || 0);
  const max = vals.length ? Math.max(...vals) : 0;
  const min = vals.length ? Math.min(...vals) : 0;

  const STOPS = [
    'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)',
    'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)',
  ];
  const level = (v) => {
    if (!v) return -1;
    const t = (v - min) / (max - min || 1);
    return Math.min(STOPS.length - 1, Math.floor(t * (STOPS.length - 1) + 0.5));
  };
  const color = (v) => {
    const i = level(v);
    return i < 0 ? 'var(--heat-0)' : STOPS[i];
  };
  const textColor = (v) => {
    const i = level(v);
    return i < 0 ? 'var(--fg-3)' : i >= 4 ? '#fff' : 'var(--fg-1)';
  };
  const REGION_BG = {
    N: 'color-mix(in srgb, var(--viz-2) 10%, transparent)',
    NE: 'color-mix(in srgb, var(--viz-3) 10%, transparent)',
    CO: 'color-mix(in srgb, var(--viz-6) 10%, transparent)',
    SE: 'color-mix(in srgb, var(--viz-1) 10%, transparent)',
    S: 'color-mix(in srgb, var(--viz-9) 10%, transparent)',
  };

  return (
    <div className="bmap-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="bmap" preserveAspectRatio="xMidYMid meet">
        {data.map((d) => {
          const x = d.col * (CELL_W + GAP);
          const y = d.row * (CELL_H + GAP);
          const v = d[valueKey] || 0;
          return (
            <g
              key={d.uf}
              className="bmap-cell"
              onClick={onSelect ? () => onSelect(d) : undefined}
            >
              <rect
                x={x}
                y={y}
                width={CELL_W}
                height={CELL_H}
                rx="6"
                fill={color(v)}
                stroke={REGION_BG[d.region]}
                strokeWidth="2"
              />
              <text
                x={x + CELL_W / 2}
                y={y + 22}
                textAnchor="middle"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, fill: textColor(v) }}
              >
                {d.uf}
              </text>
              <text
                x={x + CELL_W / 2}
                y={y + 40}
                textAnchor="middle"
                style={{ fontFamily: 'var(--font-body)', fontSize: 10.5, fill: textColor(v), opacity: 0.85 }}
              >
                {v ? v.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) : '—'}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="bmap-legend">
        <span className="caption">{label}</span>
        <div className="bmap-scale">
          {STOPS.map((c, i) => (
            <span key={i} style={{ background: c }}></span>
          ))}
        </div>
        <span className="caption tnum">
          {min.toLocaleString('pt-BR')} – {max.toLocaleString('pt-BR')}
        </span>
      </div>
    </div>
  );
}

window.BrazilTileMap = BrazilTileMap;
export default BrazilTileMap;
