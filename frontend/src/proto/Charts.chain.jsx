// Charts.chain.jsx — visualizations for the extended (chain / lead-lag)
// perspectives. The chain balance reuses the existing <SankeyChart>; these
// two cover the monthly lead-lag view.
//
//   MonthlyOverlay — two 12-month profiles on one axis, month-labelled.
//   LagBars        — signed cross-correlation by lag (−6…+6 months).

// ── MonthlyOverlay ───────────────────────────────────────────────────
//   series : [{ name, color, data: number[12] }]
//   months : string[12]
function MonthlyOverlay({ series, months, height = 280, label = 'índice (pico = 100)', markers = [] }) {
  const W = 720, H = height, P = { l: 40, r: 14, t: 16, b: 28 };
  const n = 12;
  const all = series.flatMap(s => s.data);
  const maxY = Math.max(...all, 0) * 1.08 || 1;
  const x = (i) => P.l + (i / (n - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - v / maxY) * (H - P.t - P.b);
  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (maxY / yTicks) * i);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {ticks.map((t, i) => (
        <g key={i}>
          <line className="grid" x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} />
          <text className="axis" x={P.l - 6} y={y(t) + 3} textAnchor="end">{t.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</text>
        </g>
      ))}
      {/* peak markers (vertical guides) */}
      {markers.map((mk, i) => (
        <line key={'mk' + i} x1={x(mk.month)} x2={x(mk.month)} y1={P.t} y2={H - P.b}
              stroke={mk.color} strokeWidth="1.4" strokeDasharray="4 4" opacity="0.6" />
      ))}
      {series.map((s, si) => {
        const pts = s.data.map((v, i) => `${x(i)},${y(v)}`).join(' ');
        return (
          <g key={si}>
            <polyline points={pts} fill="none" stroke={s.color} strokeWidth="2.4" strokeLinejoin="round" />
            {s.data.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r="2.4" fill={s.color} />)}
          </g>
        );
      })}
      {months.map((m, i) => (
        <text key={m} className="axis" x={x(i)} y={H - P.b + 15} textAnchor="middle">{m}</text>
      ))}
      <text className="axis-label" x={P.l} y={10}>{label}</text>
    </svg>
  );
}

// ── LagBars ──────────────────────────────────────────────────────────
//   profile : [{ lag, corr }]   (lag in months, corr in −1…1)
//   best    : { lag, corr }     (highlighted)
function LagBars({ profile, best, height = 240 }) {
  const W = 720, H = height, P = { l: 40, r: 14, t: 18, b: 34 };
  const bandW = (W - P.l - P.r) / profile.length;
  const max = 1;
  const y0 = P.t + (H - P.t - P.b) / 2;
  const yScale = (v) => y0 - (v / max) * ((H - P.t - P.b) / 2);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      <line className="axis-baseline" x1={P.l} x2={W - P.r} y1={y0} y2={y0} stroke="var(--border-strong)" />
      <text className="axis" x={P.l - 6} y={yScale(1) + 3} textAnchor="end">+1</text>
      <text className="axis" x={P.l - 6} y={y0 + 3} textAnchor="end">0</text>
      <text className="axis" x={P.l - 6} y={yScale(-1) + 3} textAnchor="end">−1</text>
      {profile.map((d, i) => {
        const xx = P.l + i * bandW;
        const isBest = best && d.lag === best.lag;
        const v = d.corr;
        const yb = v >= 0 ? yScale(v) : y0;
        const h = Math.abs(yScale(v) - y0);
        const fill = isBest ? 'var(--embrapa-green)' : (v >= 0 ? 'var(--viz-4)' : 'var(--err)');
        return (
          <g key={d.lag}>
            <rect x={xx + 3} y={yb} width={bandW - 6} height={Math.max(1, h)} fill={fill} opacity={isBest ? 1 : 0.7} rx="2">
              <title>defasagem {d.lag >= 0 ? '+' : ''}{d.lag} m: r = {d.corr.toFixed(2)}</title>
            </rect>
            <text className="axis" x={xx + bandW / 2} y={H - P.b + 15} textAnchor="middle"
                  style={isBest ? { fontWeight: 700, fill: 'var(--embrapa-green-darker)' } : null}>
              {d.lag >= 0 ? '+' : ''}{d.lag}
            </text>
          </g>
        );
      })}
      <text className="axis-label" x={P.l} y={11}>correlação (r)</text>
      <text className="axis" x={W - P.r} y={H - 4} textAnchor="end" style={{ opacity: 0.7 }}>defasagem dos embarques (meses) →</text>
    </svg>
  );
}

Object.assign(window, { MonthlyOverlay, LagBars });
