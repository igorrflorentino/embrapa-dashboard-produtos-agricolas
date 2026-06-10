// Charts.flow.jsx — generic flow / seasonality visualizations + the
// preview banner. These components are data-source agnostic: they consume
// the contracts from previewData.js and will be reused unchanged when the
// real bancos go live.

// ── PreviewBanner ─────────────────────────────────────────────────────
function PreviewBanner({ banco, capabilityNote }) {
  // Only promise a future "liberação" for a banco that ISN'T live yet. If the
  // banco passed is live (or absent), drop that clause — never claim a live
  // banco will be "liberado".
  const pending = banco && banco.status !== 'live';
  const date = pending && window.bancoMeta ? (window.bancoMeta(banco.id).maturityDate || null) : null;
  return (
    <div className="pv-banner">
      <span className="pv-badge">Pré-visualização</span>
      <span className="pv-text">
        Dados <strong>sintéticos de demonstração</strong>. {capabilityNote || ''}{' '}
        {pending
          ? <>Esta perspectiva já está construída; quando <strong>{banco.short}</strong> for
             liberado{date ? ` (${date})` : ''}, os mesmos gráficos passam a refletir dados
             reais — sem mudança de layout.</>
          : <>Os mesmos gráficos passam a refletir dados reais assim que o cruzamento ler o
             Gold real — sem mudança de layout.</>}
      </span>
    </div>
  );
}

// ── SankeyChart — simplified two-column flow diagram ──────────────────
//   nodes : [{ id, label, side:'origin'|'dest', value }]
//   links : [{ source, target, value }]
function SankeyChart({ nodes, links, height = 360, unit = '' }) {
  const W = 720, H = height, P = { t: 16, b: 16 };
  const colX = { origin: 150, dest: W - 150 };
  const nodeW = 13, gap = 10;

  const origins = nodes.filter(n => n.side === 'origin');
  const dests   = nodes.filter(n => n.side === 'dest');

  const layoutCol = (list) => {
    const total = list.reduce((s, n) => s + n.value, 0) || 1;
    const avail = H - P.t - P.b - gap * (list.length - 1);
    let y = P.t;
    const pos = {};
    list.forEach(n => {
      const h = Math.max(6, (n.value / total) * avail);
      pos[n.id] = { y, h, cy: y + h / 2 };
      y += h + gap;
    });
    return pos;
  };
  const oPos = layoutCol(origins);
  const dPos = layoutCol(dests);
  const pos = { ...oPos, ...dPos };

  const COLORS = ['var(--viz-1)','var(--viz-2)','var(--viz-3)','var(--viz-4)','var(--viz-5)','var(--viz-7)'];
  const colorOf = (id) => COLORS[origins.findIndex(o => o.id === id) % COLORS.length] || 'var(--viz-1)';

  // track running offset within each node for ribbon stacking
  const oOff = {}, dOff = {};
  origins.forEach(n => oOff[n.id] = 0);
  dests.forEach(n => dOff[n.id] = 0);

  const maxLink = Math.max(...links.map(l => l.value), 1);
  const ribbons = links.map((l, i) => {
    const s = pos[l.source], t = pos[l.target];
    if (!s || !t) return null;
    const sTotal = origins.find(o => o.id === l.source).value || 1;
    const tTotal = dests.find(d => d.id === l.target).value || 1;
    const sh = (l.value / sTotal) * s.h;
    const th = (l.value / tTotal) * t.h;
    const sy = s.y + oOff[l.source]; oOff[l.source] += sh;
    const ty = t.y + dOff[l.target]; dOff[l.target] += th;
    const x0 = colX.origin + nodeW, x1 = colX.dest;
    const mx = (x0 + x1) / 2;
    const path = `M${x0},${sy} C${mx},${sy} ${mx},${ty} ${x1},${ty} L${x1},${ty + th} C${mx},${ty + th} ${mx},${sy + sh} ${x0},${sy + sh} Z`;
    return <path key={i} d={path} fill={colorOf(l.source)} opacity={0.22 + 0.4 * (l.value / maxLink)} />;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {ribbons}
      {origins.map(n => (
        <g key={n.id}>
          <rect x={colX.origin} y={pos[n.id].y} width={nodeW} height={pos[n.id].h} rx="2" fill={colorOf(n.id)} />
          <text className="sankey-lbl" x={colX.origin - 8} y={pos[n.id].cy + 3} textAnchor="end">{n.label}</text>
        </g>
      ))}
      {dests.map(n => (
        <g key={n.id}>
          <rect x={colX.dest - nodeW} y={pos[n.id].y} width={nodeW} height={pos[n.id].h} rx="2" fill="var(--pres-gray-400)" />
          <text className="sankey-lbl" x={colX.dest + 8} y={pos[n.id].cy + 3} textAnchor="start">{n.label}</text>
        </g>
      ))}
    </svg>
  );
}

// ── MonthYearHeatmap — 12 months (cols) × years (rows) ────────────────
//   matrix : { [year]: number[12] }
function MonthYearHeatmap({ matrix, years, unit = '', height }) {
  const W = 720;
  const ROW_LABEL_W = 54, PAD_TOP = 24, PAD_BOT = 8;
  const ROW_H = 22, GAP = 3;
  const rows = years.slice().sort((a, b) => b - a);
  const H = height || (PAD_TOP + rows.length * (ROW_H + GAP) + PAD_BOT);
  const cellW = (W - ROW_LABEL_W) / 12;
  const all = rows.flatMap(y => matrix[y]);
  const max = Math.max(...all, 1), min = Math.min(...all, 0);
  const STOPS = ['var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)', 'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)'];
  const color = (v) => STOPS[Math.min(STOPS.length - 1, Math.floor(((v - min) / (max - min || 1)) * (STOPS.length - 1) + 0.5))];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart heatmap" preserveAspectRatio="xMidYMid meet">
      {window.MONTH_LABELS.map((m, i) => (
        <text key={m} className="axis" x={ROW_LABEL_W + i * cellW + cellW / 2} y={16} textAnchor="middle">{m}</text>
      ))}
      {rows.map((y, ri) => {
        const ry = PAD_TOP + ri * (ROW_H + GAP);
        return (
          <g key={y}>
            <text className="axis" x={ROW_LABEL_W - 8} y={ry + ROW_H * 0.7} textAnchor="end">{y}</text>
            {matrix[y].map((v, ci) => (
              <rect key={ci} x={ROW_LABEL_W + ci * cellW + 1} y={ry} width={cellW - 1} height={ROW_H} rx="2" fill={color(v)}>
                <title>{window.MONTH_LABELS[ci]}/{y}: {v.toLocaleString('pt-BR')} {unit}</title>
              </rect>
            ))}
          </g>
        );
      })}
    </svg>
  );
}

Object.assign(window, { PreviewBanner, SankeyChart, MonthYearHeatmap });
