// Charts.cross.jsx — visualizations specific to the cross-source view.
// Generic and data-agnostic: they consume plain { label, color, unit,
// data:[{y,v}] } series, so they work unchanged when real bancos go live.
//
//   DualAxisLineChart — up to 2 distinct units, each on its own Y axis.
//   StackedPanels     — one synced mini-panel per series (any N, any units).
//
// Base-100 normalization reuses the shared <MultiLineChart> (Charts.jsx).

// Compact axis-tick formatter — shared impl in data.js (window.fmtAxisTick).
const _csFmtAxis = window.fmtAxisTick;

// ── DualAxisLineChart ───────────────────────────────────────────────
// Groups series by `unit`. The first unit maps to the LEFT axis, the
// second to the RIGHT. (The view caps dual-axis mode at 2 distinct units.)
function DualAxisLineChart({ series, height = 320 }) {
  const W = 760, H = height, P = { l: 56, r: 60, t: 18, b: 30 };
  const years = (series[0]?.data || []).map(d => d.y);
  const units = [];
  series.forEach(s => { if (!units.includes(s.unit)) units.push(s.unit); });
  const leftUnit = units[0], rightUnit = units[1];

  const maxFor = (unit) => {
    const vals = series.filter(s => s.unit === unit).flatMap(s => s.data.map(d => d.v));
    return Math.max(...vals, 0) * 1.1 || 1;
  };
  const minFor = (unit) => {
    const vals = series.filter(s => s.unit === unit).flatMap(s => s.data.map(d => d.v));
    return Math.min(...vals, 0);
  };
  const scale = {};
  // Scale EVERY unit to its own range so no series collapses to a flat line
  // when 3+ units are selected; only the axis labels are limited to two.
  units.forEach(u => { scale[u] = { min: minFor(u), max: maxFor(u) }; });

  const x = (i) => P.l + (i / (years.length - 1 || 1)) * (W - P.l - P.r);
  const yFor = (unit, v) => {
    const sc = scale[unit] || { min: 0, max: 1 };
    return P.t + (1 - (v - sc.min) / (sc.max - sc.min || 1)) * (H - P.t - P.b);
  };

  const yTicks = 4;
  const leftTicks = Array.from({ length: yTicks + 1 }, (_, i) =>
    (scale[leftUnit]?.min ?? 0) + (((scale[leftUnit]?.max ?? 1) - (scale[leftUnit]?.min ?? 0)) / yTicks) * i);
  const rightTicks = rightUnit ? Array.from({ length: yTicks + 1 }, (_, i) =>
    (scale[rightUnit]?.min ?? 0) + (((scale[rightUnit]?.max ?? 1) - (scale[rightUnit]?.min ?? 0)) / yTicks) * i) : [];
  const xTickEvery = Math.max(1, Math.ceil(years.length / 8));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {/* gridlines + left axis (driven by the left unit) */}
      {leftTicks.map((t, i) => (
        <g key={'l' + i}>
          <line className="grid" x1={P.l} x2={W - P.r} y1={yFor(leftUnit, t)} y2={yFor(leftUnit, t)} />
          <text className="axis" x={P.l - 6} y={yFor(leftUnit, t) + 3} textAnchor="end">{_csFmtAxis(t)}</text>
        </g>
      ))}
      {/* right axis labels */}
      {rightTicks.map((t, i) => (
        <text key={'r' + i} className="axis" x={W - P.r + 6} y={yFor(rightUnit, t) + 3} textAnchor="start">{_csFmtAxis(t)}</text>
      ))}
      {/* series */}
      {series.map((s, si) => {
        const pts = s.data.map((d, i) => `${x(i)},${yFor(s.unit, d.v)}`).join(' ');
        return (
          <g key={si}>
            <polyline points={pts} fill="none" stroke={s.color} strokeWidth="2.25" strokeLinejoin="round" />
            <circle cx={x(s.data.length - 1)} cy={yFor(s.unit, s.data[s.data.length - 1].v)} r="3.2" fill={s.color} />
          </g>
        );
      })}
      {/* x ticks */}
      {years.map((yv, i) => (i % xTickEvery === 0 || i === years.length - 1) ? (
        <text key={yv} className="axis" x={x(i)} y={H - P.b + 16} textAnchor="middle">{yv}</text>
      ) : null)}
      {/* axis unit labels */}
      <text className="axis-label" x={P.l - 48} y={11} style={{ fill: 'var(--fg-2)' }}>{leftUnit || ''}</text>
      {rightUnit && <text className="axis-label" x={W - P.r + 2} y={11} textAnchor="start" style={{ fill: 'var(--fg-2)' }}>{rightUnit}</text>}
    </svg>
  );
}

// ── StackedPanels ───────────────────────────────────────────────────
// One mini line-panel per series, stacked vertically and aligned on a
// shared year axis. Handles any number of series and any mix of units.
function StackedPanels({ series, panelHeight = 96 }) {
  const W = 760, P = { l: 56, r: 14 };
  const years = (series[0]?.data || []).map(d => d.y);
  const xTickEvery = Math.max(1, Math.ceil(years.length / 8));
  const x = (i) => P.l + (i / (years.length - 1 || 1)) * (W - P.l - P.r);

  return (
    <div className="xs-panels">
      {series.map((s, si) => {
        const H = panelHeight, pt = 14, pb = 10;
        const vals = s.data.map(d => d.v);
        const max = Math.max(...vals, 0) * 1.1 || 1;
        const min = Math.min(...vals, 0);
        const y = (v) => pt + (1 - (v - min) / (max - min || 1)) * (H - pt - pb);
        const pts = s.data.map((d, i) => `${x(i)},${y(d.v)}`).join(' ');
        const area = `${P.l},${H - pb} ${pts} ${x(s.data.length - 1)},${H - pb}`;
        const last = s.data[s.data.length - 1];
        return (
          <div className="xs-panel" key={si}>
            <div className="xs-panel-head">
              <span className="xs-panel-dot" style={{ background: s.color }}></span>
              <span className="xs-panel-label">{s.label}</span>
              <span className="xs-panel-src">{s.bancoShort}</span>
              <span className="xs-panel-unit tnum">{_csFmtAxis(last?.v)} {s.unit}</span>
            </div>
            <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="none" style={{ height: H }}>
              <line className="grid" x1={P.l} x2={W - P.r} y1={y(max / 1.1)} y2={y(max / 1.1)} />
              <line className="grid" x1={P.l} x2={W - P.r} y1={y(min)} y2={y(min)} />
              <text className="axis" x={P.l - 6} y={y(max / 1.1) + 3} textAnchor="end">{_csFmtAxis(max / 1.1)}</text>
              <polygon points={area} fill={s.color} opacity="0.10" />
              <polyline points={pts} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" />
              <circle cx={x(s.data.length - 1)} cy={y(last.v)} r="3" fill={s.color} />
            </svg>
          </div>
        );
      })}
      <svg viewBox={`0 0 ${W} 22`} className="chart xs-panels-axis" preserveAspectRatio="none" style={{ height: 22 }}>
        {years.map((yv, i) => (i % xTickEvery === 0 || i === years.length - 1) ? (
          <text key={yv} className="axis" x={x(i)} y={14} textAnchor="middle">{yv}</text>
        ) : null)}
      </svg>
    </div>
  );
}

Object.assign(window, { DualAxisLineChart, StackedPanels });
