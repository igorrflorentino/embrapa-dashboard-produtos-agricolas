// Chart components — hand-rolled SVG, sized for dashboard cards. No chart library.

function LineChart({ data, height = 200, color = 'var(--viz-1)', label = 'BRL', valueKey = 'v' }) {
  const W = 560, H = height, P = { l: 36, r: 12, t: 14, b: 28 };
  const xs = data.map(d => d.y);
  const ys = data.map(d => d[valueKey]);
  const minY = 0;
  const maxY = Math.max(...ys) * 1.1;
  const x = (i) => P.l + (i / (data.length - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - (v - minY) / (maxY - minY)) * (H - P.t - P.b);
  const pts = data.map((d, i) => `${x(i)},${y(d[valueKey])}`).join(' ');
  const area = `${P.l},${H-P.b} ${pts} ${W-P.r},${H-P.b}`;
  const yTicks = 4;
  const ticks = Array.from({length: yTicks+1}, (_, i) => (maxY/yTicks)*i);
  const xTickEvery = Math.ceil(data.length / 6);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {ticks.map((t, i) => (
        <g key={i}>
          <line className="grid" x1={P.l} x2={W-P.r} y1={y(t)} y2={y(t)} />
          <text className="axis" x={P.l - 6} y={y(t) + 3} textAnchor="end">
            {t >= 1 ? t.toFixed(1) : t.toFixed(1)}
          </text>
        </g>
      ))}
      <polygon points={area} fill={color} opacity="0.10" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" />
      {data.map((d, i) => i % 4 === 0 ? (
        <circle key={i} cx={x(i)} cy={y(d[valueKey])} r="2.5" fill={color}/>
      ) : null)}
      {data.map((d, i) => (i % xTickEvery === 0 || i === data.length - 1) ? (
        <text key={'x'+i} className="axis" x={x(i)} y={H - P.b + 14} textAnchor="middle">{d.y}</text>
      ) : null)}
      <text className="axis-label" x={P.l} y={10}>{label}</text>
    </svg>
  );
}

function BarChart({ data, height = 200, color = 'var(--viz-2)', label = 't (mil)', valueKey = 'value' }) {
  const W = 560, H = height, P = { l: 60, r: 16, t: 14, b: 26 };
  const max = Math.max(...data.map(d => d[valueKey])) * 1.1;
  const bandH = (H - P.t - P.b) / data.length;
  const bw = (val) => (val / max) * (W - P.l - P.r);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {data.map((d, i) => {
        const yy = P.t + i * bandH + bandH * 0.15;
        const h = bandH * 0.7;
        return (
          <g key={d.uf || d.name}>
            <text className="axis" x={P.l - 8} y={yy + h * 0.7} textAnchor="end">
              {d.uf || d.name}
            </text>
            <rect x={P.l} y={yy} width={bw(d[valueKey])} height={h} fill={color} rx="2" />
            <text className="axis-val tnum" x={P.l + bw(d[valueKey]) + 6} y={yy + h * 0.7}>
              {d[valueKey].toLocaleString('pt-BR')}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// Donut chart for share-of-total
function Donut({ data, size = 160, valueKey = 'share' }) {
  const r = size / 2, ir = r * 0.62;
  let acc = 0;
  const total = data.reduce((s, d) => s + d[valueKey], 0);
  const slices = data.map(d => {
    const start = acc / total;
    acc += d[valueKey];
    const end = acc / total;
    const a0 = start * Math.PI * 2 - Math.PI / 2;
    const a1 = end * Math.PI * 2 - Math.PI / 2;
    const large = end - start > 0.5 ? 1 : 0;
    const x0 = r + r * Math.cos(a0), y0 = r + r * Math.sin(a0);
    const x1 = r + r * Math.cos(a1), y1 = r + r * Math.sin(a1);
    const xi0 = r + ir * Math.cos(a0), yi0 = r + ir * Math.sin(a0);
    const xi1 = r + ir * Math.cos(a1), yi1 = r + ir * Math.sin(a1);
    return {
      d: `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${xi1} ${yi1} A ${ir} ${ir} 0 ${large} 0 ${xi0} ${yi0} Z`,
      fill: d.color || 'var(--viz-1)',
      label: d.name,
      value: d[valueKey],
    };
  });

  return (
    <div className="donut-wrap">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        {slices.map((s, i) => <path key={i} d={s.d} fill={s.fill} />)}
        <circle cx={r} cy={r} r={ir - 2} fill="#fff" />
      </svg>
      <ul className="donut-legend">
        {data.map((d, i) => (
          <li key={i}>
            <span className="ldot" style={{background: d.color}}></span>
            <span className="lname">{d.name}</span>
            <span className="lval tnum">{(d[valueKey] * 100).toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

Object.assign(window, { LineChart, BarChart, Donut });
