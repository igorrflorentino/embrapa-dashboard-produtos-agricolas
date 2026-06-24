// magnitude.js — the single pt-BR magnitude threshold ladder (bi / mi / mil).
//
// Shared by the chart value axis (`ptBrMagnitude`, _base.jsx) and the KPI auto-scale
// (`window.autoScaleNum`, MetricConventions.jsx) so a value-axis tick ("15 bi") and a
// KPI card ("15 bi") for the SAME series can never drift apart — the FINDING #9 / DEDUP-7
// hazard the ladder restated in four places created. Pure + dependency-free, so the chart
// ES bundle can import it WITHOUT relying on the window globals at import time.
//
// Returns the bare {factor, suffix} kernel; each caller keeps its own spacing / rounding /
// currency-prefix / sign logic. `suffix` is '' below the 1e3 threshold.
export function magnitudeParts(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return { factor: 1e9, suffix: 'bi' };
  if (a >= 1e6) return { factor: 1e6, suffix: 'mi' };
  if (a >= 1e3) return { factor: 1e3, suffix: 'mil' };
  return { factor: 1, suffix: '' };
}
