# proto/ — vendored design-system prototype (handoff bundle, 2026-06-09)

These files are the **official Claude Design System handoff prototype**, vendored
verbatim from the bundle (`api.anthropic.com/v1/design/h/…` → "Embrapa Commodities
Design System") so the repo no longer depends on a `%TEMP%` extract.

**Reuse policy (the migration principle) — current state:**

| Group | Files | Fate |
|---|---|---|
| UI shell + views | `AppShell.jsx`, `MainScreen.jsx`, `View*.jsx`, `FilterMenu.jsx`, `FilterTriggerBar.jsx`, `MetricConventions.jsx`, `Glossary.jsx`, `DataBoundary.jsx`, atoms (`Atoms/Icon/Status/Sparkline/UnitFamily`) | **Reused as-is** (imported by `src/main.jsx`) |
| Registries + utils | `bancos.js`, `views.js`, `filtersSchema.js`, `contracts.js`, `chipFmt.js`, `urlState.js`, `csvExport.js`, `dataFilters.js`, `glossary.js`, `seriesUtils.js`, `data.js` (static registries + formatters; its leftover synthetic globals are unused but harmless) | **Reused** (registry status deltas ported in) |

The transitional files have since been **deleted** (not kept as dead weight), each replaced by an API-backed module that keeps the same `window.*` interface:

- Synthetic data layer — `dataStore.js`, `demoFixture.js`, `synthUtils.js`, `previewData.js`, `crossSource.js`, `crossAnalytics.js`, `crossChain.js`, `enrichment.js` → replaced by `src/data/*`.
- Hand-rolled SVG charts — `Charts.jsx`, `Charts.geo.jsx`, `Charts.flow.jsx`, `Charts.cross.jsx`, `Charts.chain.jsx` → replaced by Plotly.js components in `src/charts/` (identical names + props, with zoom/hover/pan).
- Prototype entry `Dashboard.html` → its inline boot script is ported into `src/main.jsx`.

Spec: `PLANS/react_migration_contract_map.md`.
