// Charts.geo.jsx — geographic and matrix visualizations
//   · BrazilTileMap   choropleth-style hex/tile map of the 27 UFs
//   · Heatmap         year × category color matrix
//   · StackedArea     stacked area for product composition over time
//   · YoYBars         year-over-year variation, signed bars
//   · FlagBars        100% stacked bar for quality flag distribution
//   · RegionBars      vertical bar chart for region totals
//   · LorenzCurve     cumulative-share curve (used by Concentração)
//
// Hand-rolled SVG — no chart library. Sized for dashboard cards.

// ────────────────────────────────────────────────────────────────────
// BrazilTileMap — geospatial choropleth on a 9-row tile grid
// ────────────────────────────────────────────────────────────────────
function BrazilTileMap({ data, valueKey = 'value', label = 'R$ mi', height = 420, onSelect }) {
  // 8 cols × 9 rows; each cell ~ 56×52
  const COLS = 8, ROWS = 9;
  const CELL_W = 60, CELL_H = 56, GAP = 4;
  const W = COLS * (CELL_W + GAP);
  const H = ROWS * (CELL_H + GAP);

  const vals = data.map(d => d[valueKey] || 0);
  const max = vals.length ? Math.max(...vals) : 0;
  const min = vals.length ? Math.min(...vals) : 0;

  // 7-step sequential scale — single source of truth (--heat-* tokens)
  const STOPS = [
    'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)',
    'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)',
  ];
  // Shared bucket index so cell fill and label color never disagree.
  const level = (v) => {
    if (!v) return -1;
    const t = (v - min) / (max - min || 1);
    return Math.min(STOPS.length - 1, Math.floor(t * (STOPS.length - 1) + 0.5));
  };
  const color = (v) => { const i = level(v); return i < 0 ? 'var(--heat-0)' : STOPS[i]; };
  const textColor = (v) => {
    const i = level(v);
    // White only from --heat-5 down (dark enough); dark ink on light cells.
    return i < 0 ? 'var(--fg-3)' : (i >= 4 ? '#fff' : 'var(--fg-1)');
  };

  // Region outline groups — faint categorical washes, driven by the viz scale
  // (regions are a categorical dimension; --viz-* is the categorical palette).
  const REGION_BG = {
    N:  'color-mix(in srgb, var(--viz-2) 10%, transparent)',
    NE: 'color-mix(in srgb, var(--viz-3) 10%, transparent)',
    CO: 'color-mix(in srgb, var(--viz-6) 10%, transparent)',
    SE: 'color-mix(in srgb, var(--viz-1) 10%, transparent)',
    S:  'color-mix(in srgb, var(--viz-9) 10%, transparent)',
  };

  return (
    <div className="bmap-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="bmap" preserveAspectRatio="xMidYMid meet">
        {data.map((d) => {
          const x = d.col * (CELL_W + GAP);
          const y = d.row * (CELL_H + GAP);
          const v = d[valueKey] || 0;
          return (
            <g key={d.uf}
               className="bmap-cell"
               onClick={onSelect ? () => onSelect(d) : undefined}>
              <rect x={x} y={y} width={CELL_W} height={CELL_H} rx="6"
                    fill={color(v)} stroke={REGION_BG[d.region]} strokeWidth="2" />
              <text x={x + CELL_W / 2} y={y + 22} textAnchor="middle"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, fill: textColor(v) }}>
                {d.uf}
              </text>
              <text x={x + CELL_W / 2} y={y + 40} textAnchor="middle"
                    style={{ fontFamily: 'var(--font-body)', fontSize: 10.5, fill: textColor(v), opacity: 0.85 }}>
                {v ? v.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) : '—'}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="bmap-legend">
        <span className="caption">{label}</span>
        <div className="bmap-scale">
          {STOPS.map((c, i) => <span key={i} style={{ background: c }}></span>)}
        </div>
        <span className="caption tnum">
          {min.toLocaleString('pt-BR')} – {max.toLocaleString('pt-BR')}
        </span>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Heatmap — year × category matrix
//   rows : array of { id, label, values: [{ y, v } ...] }
// ────────────────────────────────────────────────────────────────────
function Heatmap({ rows, valueKey = 'v', valueLabel = '', height }) {
  const W = 720;
  const ROW_LABEL_W = 120;
  const PAD_TOP = 22, PAD_BOTTOM = 22;
  const ROW_H = 22, GAP = 2;
  // No rows (e.g. all UFs filtered out) → empty plot area, never touch rows[0].
  if (!rows || rows.length === 0 || !(rows[0].values?.length)) {
    const H0 = height || (PAD_TOP + PAD_BOTTOM);
    return <svg viewBox={`0 0 ${W} ${H0}`} className="chart heatmap" preserveAspectRatio="xMidYMid meet" />;
  }
  const cols = rows[0].values.map(d => d.y);
  const cellW = (W - ROW_LABEL_W) / cols.length;
  const H = height || (PAD_TOP + rows.length * (ROW_H + GAP) + PAD_BOTTOM);

  const all = rows.flatMap(r => r.values.map(v => v[valueKey] || 0));
  const max = Math.max(...all);
  const min = Math.min(...all);
  const STOPS = ['var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)', 'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)'];
  const color = (v) => {
    if (v == null) return 'var(--heat-0)';
    const t = (v - min) / (max - min || 1);
    return STOPS[Math.min(STOPS.length - 1, Math.floor(t * (STOPS.length - 1) + 0.5))];
  };

  // Show every 4th year on x axis
  const xTickEvery = Math.max(1, Math.ceil(cols.length / 8));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart heatmap" preserveAspectRatio="xMidYMid meet">
      {rows.map((r, ri) => {
        const ry = PAD_TOP + ri * (ROW_H + GAP);
        return (
          <g key={r.id}>
            <text className="axis" x={ROW_LABEL_W - 8} y={ry + ROW_H * 0.7} textAnchor="end">{r.label}</text>
            {r.values.map((d, ci) => (
              <rect key={d.y}
                    x={ROW_LABEL_W + ci * cellW + 1}
                    y={ry}
                    width={cellW - 1}
                    height={ROW_H}
                    fill={color(d[valueKey])}
                    rx="1.5">
                <title>{r.label} · {d.y} : {(d[valueKey] || 0).toLocaleString('pt-BR')} {valueLabel}</title>
              </rect>
            ))}
          </g>
        );
      })}
      {cols.map((y, ci) => (ci % xTickEvery === 0 || ci === cols.length - 1) ? (
        <text key={y} className="axis"
              x={ROW_LABEL_W + ci * cellW + cellW / 2}
              y={H - 6}
              textAnchor="middle">{y}</text>
      ) : null)}
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// StackedArea — products as stacked layers over time
//   series : [{ code, name, color, data: [{ y, v }] }]
// ────────────────────────────────────────────────────────────────────
function StackedArea({ series, height = 260, valueKey = 'v', label = 'R$ mi' }) {
  const W = 720, H = height, P = { l: 44, r: 12, t: 14, b: 28 };
  // No series (e.g. empty basket) → render an empty plot area, never crash.
  if (!series || series.length === 0 || !(series[0]?.data?.length)) {
    return <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet" />;
  }
  const years = series[0].data.map(d => d.y);
  // total per year for normalization (we render absolute stacks)
  const totals = years.map((_, i) => series.reduce((s, sr) => s + (sr.data[i][valueKey] || 0), 0));
  const maxY = (Math.max(...totals) * 1.05) || 1;
  const x = (i) => P.l + (i / (years.length - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - v / maxY) * (H - P.t - P.b);

  // Compute cumulative per layer
  const layers = series.map((sr, si) => {
    const top = sr.data.map((_, i) => {
      let acc = 0;
      for (let k = 0; k <= si; k++) acc += series[k].data[i][valueKey] || 0;
      return acc;
    });
    const bottom = sr.data.map((_, i) => {
      let acc = 0;
      for (let k = 0; k < si; k++) acc += series[k].data[i][valueKey] || 0;
      return acc;
    });
    const pts = [
      ...top.map((v, i) => `${x(i)},${y(v)}`),
      ...bottom.map((v, i) => `${x(i)},${y(v)}`).reverse(),
    ].join(' ');
    return { ...sr, pts };
  });

  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (maxY / yTicks) * i);
  const xTickEvery = Math.max(1, Math.ceil(years.length / 7));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {ticks.map((t, i) => (
        <g key={i}>
          <line className="grid" x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} />
          <text className="axis" x={P.l - 6} y={y(t) + 3} textAnchor="end">
            {t.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}
          </text>
        </g>
      ))}
      {layers.map((l, i) => (
        <polygon key={i} points={l.pts} fill={l.color} opacity={0.92}>
          <title>{l.name}</title>
        </polygon>
      ))}
      {years.map((yv, i) => (i % xTickEvery === 0 || i === years.length - 1) ? (
        <text key={yv} className="axis" x={x(i)} y={H - P.b + 14} textAnchor="middle">{yv}</text>
      ) : null)}
      <text className="axis-label" x={P.l} y={10}>{label}</text>
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// YoYBars — year-over-year variation, signed
// ────────────────────────────────────────────────────────────────────
function YoYBars({ data, valueKey = 'v', height = 200 }) {
  const W = 720, H = height, P = { l: 36, r: 12, t: 14, b: 28 };
  if (!data || data.length === 0) {
    return <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet" />;
  }
  // prev === 0 (or missing) → 0% rather than a divide-by-zero NaN/Infinity.
  const yoy = data.map((d, i) => {
    const prev = i === 0 ? null : data[i - 1][valueKey];
    return { y: d.y, pct: (i === 0 || !prev) ? 0 : ((d[valueKey] - prev) / prev) * 100 };
  });
  const max = (Math.max(...yoy.map(d => Math.abs(d.pct))) * 1.15) || 1;
  const bandW = (W - P.l - P.r) / yoy.length;
  const y0 = P.t + (H - P.t - P.b) / 2;
  const yScale = (v) => y0 - (v / max) * ((H - P.t - P.b) / 2);

  const xTickEvery = Math.max(1, Math.ceil(yoy.length / 8));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      <line className="axis-baseline" x1={P.l} x2={W - P.r} y1={y0} y2={y0} />
      <text className="axis" x={P.l - 6} y={y0 + 3} textAnchor="end">0%</text>
      <text className="axis" x={P.l - 6} y={yScale(max) + 3} textAnchor="end">+{max.toFixed(0)}</text>
      <text className="axis" x={P.l - 6} y={yScale(-max) + 3} textAnchor="end">−{max.toFixed(0)}</text>

      {yoy.slice(1).map((d, i) => {
        const xx = P.l + (i + 1) * bandW;
        const v = d.pct;
        const ybar = v >= 0 ? yScale(v) : y0;
        const h = Math.abs(yScale(v) - y0);
        const fill = v >= 0 ? 'var(--ok)' : 'var(--err)';
        return (
          <rect key={d.y} x={xx + 2} y={ybar} width={bandW - 4} height={h} fill={fill} opacity="0.85" rx="1">
            <title>{d.y}: {v >= 0 ? '+' : ''}{v.toFixed(1)}%</title>
          </rect>
        );
      })}
      {yoy.map((d, i) => (i % xTickEvery === 0 || i === yoy.length - 1) ? (
        <text key={d.y} className="axis" x={P.l + i * bandW + bandW / 2} y={H - P.b + 14} textAnchor="middle">{d.y}</text>
      ) : null)}
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// FlagBars — 100% stacked horizontal bars (per product / per UF)
// ────────────────────────────────────────────────────────────────────
function FlagBars({ rows, flags, labelKey = 'name', height }) {
  const W = 720;
  const ROW_LABEL_W = 170;
  // Reserve a right-hand gutter for the per-row % label so it is not clipped
  // by the SVG viewBox edge (labels are start-anchored just past the track).
  const VAL_W = 42;
  const BAR_H = 22, GAP = 8, PAD_TOP = 14, PAD_BOT = 14;
  const H = height || (PAD_TOP + rows.length * (BAR_H + GAP) + PAD_BOT);
  const trackW = W - ROW_LABEL_W - 12 - VAL_W;
  // No rows or no flags selected → empty plot area, never crash on flags[0].
  if (!rows || rows.length === 0 || !flags || flags.length === 0) {
    return <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet" />;
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {rows.map((r, ri) => {
        const ry = PAD_TOP + ri * (BAR_H + GAP);
        let acc = 0;
        const ok = (flags[0] && r[flags[0].id]) || 0;
        return (
          <g key={r.code || r.uf || r[labelKey]}>
            <text className="axis" x={ROW_LABEL_W - 8} y={ry + BAR_H * 0.7} textAnchor="end">{r[labelKey]}</text>
            {flags.map((f) => {
              const v = r[f.id] || 0;
              const x = ROW_LABEL_W + acc * trackW;
              const w = v * trackW;
              acc += v;
              return (
                <rect key={f.id} x={x} y={ry} width={w} height={BAR_H} fill={f.color} rx="1">
                  <title>{r[labelKey]} · {f.label}: {(v * 100).toFixed(1)}%</title>
                </rect>
              );
            })}
            <text className="axis-val tnum"
                  x={ROW_LABEL_W + trackW + 8}
                  y={ry + BAR_H * 0.7}
                  style={{ fill: ok > 0.85 ? 'var(--ok)' : ok > 0.7 ? 'var(--fg-1)' : 'var(--warn)' }}>
              {(ok * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// RegionBars — vertical bars for region totals
// ────────────────────────────────────────────────────────────────────
function RegionBars({ data, valueKey = 'value', label = 'R$ mi', height = 220 }) {
  const W = 520, H = height, P = { l: 36, r: 12, t: 18, b: 38 };
  const max = (Math.max(...data.map(d => d[valueKey])) * 1.12) || 1;
  const bandW = (W - P.l - P.r) / data.length;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {data.map((d, i) => {
        const x = P.l + i * bandW + bandW * 0.18;
        const w = bandW * 0.64;
        const h = (d[valueKey] / max) * (H - P.t - P.b);
        const y = H - P.b - h;
        return (
          <g key={d.id}>
            <rect x={x} y={y} width={w} height={h} fill={d.color} rx="3" />
            <text className="axis-val tnum" x={x + w / 2} y={y - 6} textAnchor="middle">
              {d[valueKey].toLocaleString('pt-BR')}
            </text>
            <text className="axis" x={x + w / 2} y={H - P.b + 14} textAnchor="middle">{d.label}</text>
            <text className="axis"
                  x={x + w / 2}
                  y={H - P.b + 28}
                  textAnchor="middle"
                  style={{ opacity: 0.7, fontSize: 10 }}>
              {d.ufs} UF
            </text>
          </g>
        );
      })}
      <text className="axis-label" x={P.l} y={12}>{label}</text>
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// LorenzCurve — cumulative share of value vs cumulative share of units.
//   values : number[]  (e.g. per-UF or per-product value)
function LorenzCurve({ values, height = 300, color = 'var(--embrapa-green)', xLabel = 'unidades', yLabel = 'valor' }) {
  const W = 420, H = height, P = { l: 44, r: 16, t: 16, b: 36 };
  const sorted = values.slice().filter(v => v > 0).sort((a, b) => a - b);
  const n = sorted.length;
  const total = sorted.reduce((s, v) => s + v, 0) || 1;
  // cumulative points (0,0) … (1,1)
  const pts = [{ x: 0, y: 0 }];
  let acc = 0;
  sorted.forEach((v, i) => {
    acc += v;
    pts.push({ x: (i + 1) / n, y: acc / total });
  });
  const x = (fx) => P.l + fx * (W - P.l - P.r);
  const y = (fy) => P.t + (1 - fy) * (H - P.t - P.b);
  const lorenz = pts.map(p => `${x(p.x)},${y(p.y)}`).join(' ');
  const areaPts = `${x(0)},${y(0)} ${lorenz} ${x(1)},${y(0)}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {[0.25, 0.5, 0.75, 1].map(t => (
        <g key={t}>
          <line className="grid" x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} />
          <text className="axis" x={x(0) - 6} y={y(t) + 3} textAnchor="end">{(t * 100).toFixed(0)}%</text>
        </g>
      ))}
      {/* line of equality */}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--fg-3)" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.6" />
      {/* lorenz area + curve */}
      <polygon points={areaPts} fill={color} opacity="0.12" />
      <polyline points={lorenz} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" />
      {[0.25, 0.5, 0.75, 1].map(t => (
        <text key={'x'+t} className="axis" x={x(t)} y={H - P.b + 14} textAnchor="middle">{(t * 100).toFixed(0)}%</text>
      ))}
      <text className="axis-label" x={x(0)} y={10}>{yLabel} acum.</text>
      <text className="axis" x={x(1)} y={H - 6} textAnchor="end" style={{ opacity: 0.7 }}>{xLabel} acum. →</text>
    </svg>
  );
}

Object.assign(window, { BrazilTileMap, Heatmap, StackedArea, YoYBars, FlagBars, RegionBars, LorenzCurve });
