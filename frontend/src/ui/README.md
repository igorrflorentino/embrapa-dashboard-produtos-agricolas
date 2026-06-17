# ui/ — the dashboard's React UI layer

This directory is the **live production UI** of the dashboard: the app shell, every
view/perspective, the FilterMenu, the client-side registries (`bancos.js`,
`views.js`, `filtersSchema.js`), and the view-model utilities (`dataFilters.js`,
`urlState.js`, `chipFmt.js`, `csvExport.js`, …). `src/main.jsx` imports these
modules at boot; Vite bundles them into `dist/`, which the Flask service serves on
Cloud Run. **This is not a prototype** — it ships to users.

## Origin

The code was originally delivered as the **Claude Design System handoff prototype**
("Embrapa Commodities Design System") and adopted into the repo verbatim, so the
build no longer depends on an external bundle. We keep it close to the handoff (it
is intentionally **out of ESLint scope** — see `frontend/eslint.config.js` — and we
avoid restyling it), but it runs in production like any other source.

## What it does NOT contain

The two trees we author and maintain live OUTSIDE this directory:

| Concern | Lives in | Replaced this directory's… |
|---|---|---|
| Data access (API-backed) | `src/data/` (`dataStore`, `producers`, `enrichment`, `decorate`, `resource`) | …synthetic data layer (the old `dataStore.js`, `demoFixture.js`, `crossSource.js`, … — deleted) |
| Analytical charts | `src/charts/` (Plotly.js + SVG ports) | …hand-rolled SVG charts (`Charts*.jsx` — deleted) |

The synthetic mock series the prototype shipped with (`OVERVIEW_TS`, `PRODUCT_TS`,
the `QUALITY_*`/`TOP_*` tables) were removed once the views moved to the API-backed
snapshot. `data.js` here now holds only the live client-side **registries** (the UF
tile grid, region + quality-flag taxonomies, the unit-family conversion table) and
the pt-BR **formatters** — the metadata the `/api` deliberately omits, joined onto
the API rows in `src/data/decorate.js`.

## Contract

The boundary between this UI and the data layer is the `window.*` global interface
(`window.applyFilters`, `window.dataStore`, the producers, the registries). The
snapshot/contract shapes are documented in `contracts.js` and
`PLANS/react_migration_contract_map.md` (the historical migration spec).
