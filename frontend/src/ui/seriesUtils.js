// seriesUtils.js — shared series analytics + the categorical viz scale.
//
// Single source of truth for the comparison perspectives (ViewProductCompare,
// ViewCrossSource) and any chart that paints a categorical series. These
// helpers used to be COPY-PASTED verbatim across those views (growth /
// pearson / cagr / corrColor) and the 10-stop color array was duplicated in
// dataFilters.js and ViewValueVolume.jsx. Centralised here so a fix lands in
// one place. Loaded right after data.js (see src/main.jsx import order).

// ── Categorical color scale (the 10-stop --viz ramp) ───────────────────
// Token references only — never raw hex (see colors_and_type.css · --viz-*).
// Consumers that need overflow stops append their own grays.
window.VIZ_SCALE = [
  'var(--viz-1)', 'var(--viz-2)', 'var(--viz-3)', 'var(--viz-4)', 'var(--viz-5)',
  'var(--viz-6)', 'var(--viz-7)', 'var(--viz-8)', 'var(--viz-9)', 'var(--viz-10)',
];
// i-th categorical color, wrapping around the scale.
window.vizColor = (i) => window.VIZ_SCALE[((i % window.VIZ_SCALE.length) + window.VIZ_SCALE.length) % window.VIZ_SCALE.length];

// ── Series statistics ──────────────────────────────────────────────────
// Year-over-year growth array from a list of points (default value key 'v').
window.seriesGrowth = (pts, key = 'v') =>
  (pts || []).slice(1).map((d, i) => (pts[i][key] ? (d[key] - pts[i][key]) / pts[i][key] : 0));

// Pearson correlation between two equal-intent arrays (truncated to the
// shorter length). Returns 0 when undefined (n < 2 or zero variance).
window.pearson = (a, b) => {
  const n = Math.min(a.length, b.length);
  if (n < 2) return 0;
  const ma = a.reduce((s, x) => s + x, 0) / n;
  const mb = b.reduce((s, x) => s + x, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { const xa = a[i] - ma, xb = b[i] - mb; num += xa * xb; da += xa * xa; db += xb * xb; }
  return (da && db) ? num / Math.sqrt(da * db) : 0;
};

// Year-aware Pearson on YoY growth: aligns the two point series by their YEAR
// (point.y), NOT by array index, then correlates growth over the common,
// calendar-adjacent year pairs. The plain index pairing (pearson(seriesGrowth(a),
// seriesGrowth(b))) silently misaligns the moment one series has an internal year
// gap. For gap-free, same-year series this returns exactly the old result.
window.pearsonByYear = (ptsA, ptsB, key = 'v') => {
  const ma = new Map((ptsA || []).map(d => [d.y, d[key]]));
  const mb = new Map((ptsB || []).map(d => [d.y, d[key]]));
  const years = [...ma.keys()].filter(y => mb.has(y)).sort((x, y) => x - y);
  const ga = [], gb = [];
  for (let i = 1; i < years.length; i++) {
    if (years[i] - years[i - 1] !== 1) continue;  // growth only across adjacent years
    const a0 = ma.get(years[i - 1]), a1 = ma.get(years[i]);
    const b0 = mb.get(years[i - 1]), b1 = mb.get(years[i]);
    ga.push(a0 ? (a1 - a0) / a0 : 0);
    gb.push(b0 ? (b1 - b0) / b0 : 0);
  }
  return window.pearson(ga, gb);
};

// Compound annual growth rate, in PERCENT, over `periods` intervals.
window.cagrPct = (v0, vT, periods) => {
  const p = periods || 1;
  return v0 > 0 ? (Math.pow(vT / v0, 1 / p) - 1) * 100 : 0;
};
// Accumulated change from v0 to vT, in PERCENT.
window.accumPct = (v0, vT) => (v0 > 0 ? ((vT - v0) / v0) * 100 : 0);

// Ordinary-least-squares linear trend over points keyed by `.y` (x = year) and a
// value key. Returns { slope, intercept, predict(x), line } where `line` is the
// two endpoints [{y:xmin,…},{y:xmax,…}] ready to plot as a straight dashed trace
// (the "linha de tendência" overlay). Returns null when fewer than 2 finite points
// or zero x-variance — the caller then simply draws no trend line.
window.linearFit = (pts, key = 'v') => {
  const xs = [], ys = [];
  (pts || []).forEach((d) => {
    const x = Number(d.y), y = Number(d[key]);
    if (Number.isFinite(x) && Number.isFinite(y)) { xs.push(x); ys.push(y); }
  });
  const n = xs.length;
  if (n < 2) return null;
  const mx = xs.reduce((s, x) => s + x, 0) / n;
  const my = ys.reduce((s, y) => s + y, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { const dx = xs[i] - mx; num += dx * (ys[i] - my); den += dx * dx; }
  if (!den) return null;
  const slope = num / den;
  const intercept = my - slope * mx;
  const predict = (x) => slope * x + intercept;
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  return { slope, intercept, predict, line: [{ y: x0, [key]: predict(x0) }, { y: x1, [key]: predict(x1) }] };
};

// Correlation-cell tint. Positive → institutional green, negative → terracotta
// error token, alpha scaled by |r| (0.12 floor → 0.72 at |r|=1). Token-driven
// via color-mix so it tracks the palette — never a raw rgba() literal.
window.corrColor = (r) => {
  const token = r >= 0 ? 'var(--ok)' : 'var(--err)';
  const pct = Math.round((0.12 + Math.abs(r) * 0.6) * 100);
  return `color-mix(in srgb, ${token} ${pct}%, transparent)`;
};
