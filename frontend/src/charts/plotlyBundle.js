// plotlyBundle.js — a custom partial Plotly.js bundle (not the 3MB full dist).
// Registers only the trace types the dashboard's charts use, plus the pt-BR
// locale. Every chart imports Plotly from here.
//
// Trace coverage (see PLANS/react_migration_contract_map.md §4):
//   scatter → line / area / multi-line / lorenz / overlay / dual-axis / panels
//   bar     → bar / YoY / flag-bars / region-bars / lag-bars
//   pie     → donut
//   heatmap → heatmap / month-year / tile-map (choropleth on a grid)
//   sankey  → flows / chain balance

import Plotly from 'plotly.js/lib/core';
import scatter from 'plotly.js/lib/scatter';
import bar from 'plotly.js/lib/bar';
import pie from 'plotly.js/lib/pie';
import heatmap from 'plotly.js/lib/heatmap';
import sankey from 'plotly.js/lib/sankey';
import ptBR from 'plotly.js/lib/locales/pt-br';

Plotly.register([scatter, bar, pie, heatmap, sankey]);
Plotly.register(ptBR);

export default Plotly;
