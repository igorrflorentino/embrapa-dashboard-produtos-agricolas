// plotlyBundle.js — a custom partial Plotly.js bundle (not the 3MB full dist).
// Registers only the trace types the dashboard's charts use, plus the pt-BR
// locale. Every chart imports Plotly from here.
//
// Trace coverage (see PLANS/react_migration_contract_map.md §4):
//   scatter → line / area / multi-line / lorenz / overlay / dual-axis / panels
//   bar     → bar / YoY / flag-bars / region-bars / lag-bars
//   heatmap → heatmap / month-year / tile-map (choropleth on a grid)
//   sankey  → flows / chain balance
// NOTE: the share/composition Donut is a pure-SVG component (Donut.jsx) — no
// chart emits a Plotly `type: 'pie'` — so the `pie` trace is intentionally NOT
// bundled here. Re-add `plotly.js/lib/pie` only if a real Plotly pie/donut lands.

import Plotly from 'plotly.js/lib/core';
import scatter from 'plotly.js/lib/scatter';
import bar from 'plotly.js/lib/bar';
import heatmap from 'plotly.js/lib/heatmap';
import sankey from 'plotly.js/lib/sankey';
import ptBR from 'plotly.js/lib/locales/pt-br';

Plotly.register([scatter, bar, heatmap, sankey]);
Plotly.register(ptBR);

export default Plotly;
