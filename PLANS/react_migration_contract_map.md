# React Migration — Contract Map (the single spec)

> Status: **authoritative**. Replaces the stalled extraction workflow; built from ground
> truth — `frontend/src/proto/contracts.js` (shapes), `dashboard/seam.py` (BFF output),
> `serving/sql.py` (exact gateway columns), and a full read of the reused views +
> producers. Decision of record: migrate the dashboard from Dash to a **React SPA over a
> Flask REST API**, charts in **Plotly.js** (zoom/hover/pan). Dash is removed at the end.

## 0. Architecture decisions

1. **The API emits the full per-banco `BancoSnapshot`; filtering stays client-side.**
   The reused views read `window.applyFilters(summary, bancoId)` (`dataFilters.js`), which
   narrows the *full* snapshot in JS (year window, basket, states, flags). The serving marts
   are already pre-aggregated to annual/product/UF grain (small), so shipping the whole
   snapshot honors Pushdown — the heavy aggregation already happened in BigQuery. We do **not**
   reimplement `applyFilters` in Python. `dataStore.js` + `dataFilters.js` are reused unchanged.

2. **Conventions (currency × correction) are applied SERVER-SIDE via column selection.**
   The prototype faked correction with a single client multiplier on a canonical value — wrong
   for a research tool whose point is real per-year deflation. The marts carry precomputed
   `val_real_{ipca,igpm,igpdi}_brl`, `val_yearfx_{brl,usd}`. `seam.effective_value_column(banco, conv)`
   already maps (currency, correction) → the right column with a documented fallback. So the
   **snapshot fetch is parameterized by `currency` + `correction`**; changing either re-fetches.
   The client-side `convFactor` for currency/correction is **neutralized to 1.0** (server already
   applied it); the physical-unit conversion (`massQtyMul`/`volumeQtyMul`) and `autoScale`
   magnitude abbreviation stay client-side. → small required patch to `MetricConventions.jsx` (§6).
   EUR/CNY have no real column → seam falls back to BRL with a label note (honest).

3. **Client-side registries stay in the frontend** — they are presentation metadata, not data:
   UF tile coords (`col`/`row`) + region names (`UF_DATA`/`REGIONS`), quality-flag `label`/`color`
   (`QUALITY_FLAGS`), `VIZ_SCALE` colors, the `bancos.js`/`views.js`/`filtersSchema.js` registries,
   and the `MetricConventions` factor tables. The API returns the *keys* to join on (`uf`, flag
   `id`); the JS data layer decorates with `col`/`row`/`label`/`color`. Joining server-side would
   duplicate registries and invite drift.

4. **Magnitudes the API emits match the prototype's internal scale** so reused views work
   unchanged: `productTS.v` in **millions**, `overviewTS.v` in **billions**, mass quantity in
   **mil t** (÷1e3 from t), volume in **mi m³** (÷1e6 from m³), `ufData.value` in **millions**.
   Verified at `dataFilters.js:99` (`ts.v = productTS.v / 1000`).

## 1. REST API (`/api/*`, blueprint in `webapi/routes.py`)

All GET unless noted. `banco` ∈ {`ibge_pevs`,`mdic_comex`,`un_comtrade`}. Responses are JSON in
contracts.js shape. `preview:false` on all live producers (real data).

| Endpoint | Params | seam fn | Response (contracts.js typedef) |
|---|---|---|---|
| `/catalog` | — | `commodity_catalog()` | `{cid:{id,name,pevs[],comex[],comtrade[]}}` ✅ done |
| `/source-meta` | `banco` | `source_meta(banco)` | provenance row dict ✅ done |
| `/snapshot` | `banco,currency,correction` | `snapshot(banco,conv)` *(summary=None → full)* | `BancoSnapshot` (§2) |
| `/cross/metric-refs` | — | `cross_metric_refs()` | `[{banco,banco_short,metric,label,family}]` |
| `/cross/series` | `banco,metric,y0?,y1?` | `cross_series(banco,metric,y0,y1)` | `SeriesResult` — `points` already in display unit |
| `/cross/export-coef` | `commodity?` | `export_coefficient(commodity)` | `ExportCoefficient` (camel `byUf`) |
| `/cross/market-share` | `commodity?` | `market_share(commodity)` | `MarketShare` (camel `byProduct`) |
| `/cross/price-spread` | `commodity?` | `price_spread(commodity)` | `PriceSpread` |
| `/cross/mirror` | `commodity?` | `trade_mirror(commodity)` | `TradeMirror` |
| `/cross/value-added` | `commodity?` | `value_added(commodity)` | `ValueAddedAnalysis` (add `years`,`byLevel`,`priceB/P`) |
| `/curation/worklist` | — | `curation_worklist()` | `{rows[],total,classified,pending,by_level}` |
| `/curation/code-level` | **POST** `{source,code,level}` | `record_code_level(...)` | writer result; author via IAP (`webapi/auth.current_author`) |

**Data-blocked** (no source): `chainBalance`, `harvestShipmentLag`, `marketNatureAnalysis`,
and the regime×flow market-nature axis. These ship honest in-product placeholders client-side
(no endpoint) until SEFAZ inter-UF flows / monthly PEVS / the customs-procedure dim exist.

## 2. `/snapshot` serializer (`webapi/serializers.py`) — gateway columns → contracts.js

`seam.snapshot(banco, conv, summary=None)` returns DataFrames keyed `products, product_ts,
overview_ts, uf_data, quality` + `value_label`. Reshape (per-family q-scale where noted):

- **products** ← `products` df cols `{code,name,unit,unit_native,family}` → `[{code,name,unit,family}]`.
- **productTS** ← `product_ts` cols `{code,reference_year,total_value,total_qty_native,family}`,
  GROUP BY `code` → `{code: [{y:reference_year, v:total_value/1e6, q:total_qty_native/(1e3 if family=='massa' else 1e6), family}]}`.
  Map family `'massa'→'mass'`, `'volume'→'volume'` (contracts.js uses `mass`).
- **overviewTS** ← `overview_ts` cols `{reference_year,total_value,q_mass,q_vol}` →
  `[{y:reference_year, v:total_value/1e9, q:q_mass/1e3, q_mass:q_mass/1e3, q_vol:q_vol/1e6}]`.
- **ufData** ← `uf_data` cols `{state_acronym,state_name,region,region_abbrev,total_value}` →
  `[{uf:state_acronym, name:state_name, region:region_abbrev, value:total_value/1e6, q_mass:0, q_vol:0}]`.
  *(col/row added client-side from `UF_DATA`. Per-UF quantity is a known gap — `production_by_uf`
  returns no quantity; q_mass/q_vol=0 until a family-aware per-UF reader exists.)*
- **quality** ← `quality` cols `{source,data_quality_flag,n_rows,share}` →
  `[{id:data_quality_flag, count:n_rows, share}]` *(label/color added client-side from QUALITY_FLAGS;
  confirm `share` is a 0-1 fraction in the mart — fmtPct ×100 expects that)*.
- Trade bancos: `snapshot` already renames `total_value_usd→total_value`; `uf_data` only for COMEX.
- `qualityTs`/`qualityByProduct`/`qualityByUf`/`topMunis` not yet served (optional keys) → omit or `[]`.

**Cross-analytics** (already near-shape): pass through with snake→camel (`by_product→byProduct`,
`by_uf→byUf`) and add `preview:false`. `value_added` needs derived `years`, `byLevel`
(`{bruta:[{y,v}],processada:[{y,v}]}` from series `brutaV`/`procV`), `priceB`/`priceP`.
`cross_series.points[].v` is **already display magnitude** (don't rescale); add `preview:false`,
`bancoMeta`/`metricMeta` joined client-side from `bancos.js`.

## 3. JS data layer (`frontend/src/data/*.js`) — replace synthetic bodies, keep `window.*`

Reuse `dataStore.js`/`dataFilters.js`. Replace ONLY the producer bodies with API-backed ones,
keeping identical names/signatures (the `window.*` surface the views call):

- `dataStore.load(bancoId, conv)` → `fetch('/api/snapshot?banco='+id+'&currency='+c+'&correction='+k)`;
  on success cache `{status:'ready', data: decorate(json)}`. `decorate` joins `col/row/region`
  from `UF_DATA` onto `ufData` (by `uf`) and `label/color` from `QUALITY_FLAGS` onto `quality`
  (by `id`). Re-load when conventions' currency/correction changes.
- `window.snapshotFor` → for non-PEVS fallback, same fetch (dataStore is the primary path now).
- `flowData/partnerData/monthlyData(bancoId, summary)` → fetch `/api/flow|partners|monthly`
  *(endpoints: add in routes; seam fns `flow_data`/`partner_data`/`monthly_data` exist)*; decorate
  labels from `bancoDim`. **(Trade endpoints deferred — add when wiring ViewFlows/Partners/Seasonality.)**
- `crossSeries/crossCommonWindow` → `/cross/series`,`/cross/metric-refs`; `bancoMeta`/`metricMeta`
  from registries client-side.
- `exportCoefficient/marketShare/priceSpread/tradeMirror/valueAddedAnalysis` → `/cross/*`.
- `chainBalance/harvestShipmentLag/marketNatureAnalysis` → keep returning a `preview:true`
  placeholder (data-blocked); the views already render an honest banner.
- `enrichment.*` (curation) → `codes()` from `/curation/worklist`; `setCode/apply` POST
  `/curation/code-level`. Keep the optimistic draft/commit UX.

### 3.1 Sync-over-async gating (the critical frontend design)

The reused views call producers **synchronously** during render and use the result immediately
(`const r = window.crossSeries(b,m,{})`). API calls are async. Bridge WITHOUT refactoring the
reused views:

- **Per-banco path (overview/value/geo/concentration/quality/profile)** — already solved. The
  reused `DataBoundary.useBancoData(banco)` calls `dataStore.load(banco, conv)` (async) and gates
  rendering on status; the view then reads `dataStore.get(banco)` (sync) via `applyFilters`.
  Migration: make `dataStore.load` fetch `/api/snapshot` and cache the decorated snapshot.
  Re-load when conventions' currency/correction change (key the cache by `banco|currency|correction`).
- **Cross-source / analytics / curation views** — have **no gate** (they get `{view}` props and call
  producers directly). Add a thin **preload gate** (new glue, NOT a change to the reused views):
  a `CrossBoundary({view, commodity})` wrapper that, on mount/commodity-change, fires the needed
  fetches into a module cache and shows the loading state until resolved; then renders the reused
  view. The producers (`crossSeries`, `exportCoefficient`, …) become **sync cache reads**: return the
  cached value if present, else a `{preview, …, _pending:true}` placeholder + kick off the fetch +
  `notify()` subscribers (the boundary re-renders → cache now hot → view reads real data). One
  generic helper backs this: `resource(key, urlFactory)` → `{get(key), ensure(key), subscribe}`.
- **Mount the boundary at the router seam** (in the new `main.jsx`/a small `MainScreen` wrapper),
  not inside the reused views. The cross views stay byte-for-byte reused.
- **Curation** is read+write: `enrichment.codes()` reads the worklist resource; `setCode`/`apply`
  POST and then invalidate the worklist resource + `notify()` (optimistic draft UX preserved).

## 4. Chart → Plotly.js components (`frontend/src/charts/`) — same names + props as Charts*.jsx

Each replaces a hand-rolled SVG with a Plotly.js trace, identical export name + props, theme from
CSS vars (`--viz-*`, fonts) read via `getComputedStyle`. Sparkline stays SVG (tiny, no interaction).

| Component | Plotly type | props (unchanged) |
|---|---|---|
| `LineChart` | scatter (lines+fill) | `data:[{y,[valueKey]}], valueKey='v', label, color, height` |
| `MultiLineChart` | scatter ×N | `series:[{name,color,data:[{y,v}]}], valueKey, label` |
| `BarChart` | bar (horizontal) | `data:[{uf|name,[valueKey]}], valueKey='value', color` |
| `Donut` | pie hole=.6 | `data:[{name,color,[valueKey]}], valueKey='share'` |
| `StackedArea` | scatter stackgroup | `series:[{name,color,data:[{y,[valueKey]}]}], valueKey` |
| `YoYBars` | bar (signed) | `data:[{y,[valueKey]}]` (compute YoY) |
| `BrazilTileMap` | heatmap/scatter on 8×9 grid | `data:[{uf,col,row,region,[valueKey]}], valueKey, onSelect?` |
| `Heatmap` | heatmap | `rows:[{id,label,values:[{y,v}]}], valueKey` |
| `MonthYearHeatmap` | heatmap | `matrix:{year:[12]}, years, unit` |
| `FlagBars` | bar (100% stacked horiz) | `rows:[{...flagId:frac}], flags:[{id,label,color}], labelKey` |
| `RegionBars` | bar (vertical) | `data:[{id,label,color,[valueKey],ufs}], valueKey` |
| `LorenzCurve` | scatter + diagonal | `values:number[], xLabel, yLabel` |
| `SankeyChart` | sankey | `nodes:[{id,label,side,value}], links:[{source,target,value}], unit` |
| `DualAxisLineChart` | scatter, 2 yaxes | `series:[{label,color,unit,bancoShort,data:[{y,v}]}]` (group by unit) |
| `StackedPanels` | subplots | `series:[...], panelHeight` |
| `MonthlyOverlay` | scatter ×2 | `series:[{name,color,data:[12]}], months, markers` |
| `LagBars` | bar (signed) | `profile:[{lag,corr}], best` |

Use a Plotly **partial bundle** (`plotly.js-dist-min` or custom) — scatter/bar/pie/sankey/heatmap.
Shared layout helper: transparent bg, CSS-var colors, `displayModeBar` on hover, pan/zoom enabled,
unified hover, pt-BR number locale.

## 5. Boot (`frontend/src/main.jsx`) — port `Dashboard.html` inline script

Order of side-effect imports (each proto module assigns `window.*` at import): registries
(`bancos`,`views`,`filtersSchema`,`glossary`,`urlState`,`chipFmt`,`seriesUtils`,`dataFilters`,
`csvExport`) → **new** `src/data/*` (replaces synthetic `data/dataStore/previewData/crossSource/
crossAnalytics/crossChain/enrichment`) → **new** `src/charts/*` (replaces `Charts*`) → shell+views
(`Atoms`,`Icon`,`Status`,`Sparkline`,`UnitFamily`,`DataBoundary`,`AppShell`,`MainScreen`,`View*`,
`FilterMenu`,`FilterTriggerBar`,`MetricConventions`,`Glossary`) → mount `<Dashboard/>` with
`readStateFromURL()`. `window.React`/`window.ReactDOM` set first (proto uses globals, no imports).

## 6. Required reused-code patch — `MetricConventions.jsx`

`convFactor(conv)` must return **1.0 for the currency×correction component** (server now serves the
correct deflated column) while keeping unit conversion + autoScale. Concretely: drop
`CORRECTION_FACTOR[correction] × CURRENCY_FX[currency].rate` from the value path; keep
`massQtyMul`/`volumeQtyMul` and `scaleSeries`/`autoScaleNum`. Currency/correction selectors still
drive the `/snapshot` re-fetch (via dataStore). This is the only semantic change to reused code.

## 7. Deploy cutover (task #7)

Multi-stage image in `deploy/dashboard/` (or new `deploy/webapi/`): node stage `npm ci && npm run
build` → `frontend/dist`; python stage `uv sync --extra webapi`, copy `dist`, set
`SPA_DIST_DIR=/app/frontend/dist`, run `gunicorn embrapa_commodities.webapi.app:app`. Same Cloud
Run **Service**, same IAP, same runtime SA `sa-web-dashboard-prod`. User triggers the deploy.

## 8. Task order

#3 serializers+routes (snapshot+cross+curation) → test vs BQ · #4 `src/data/*` + dataStore patch ·
#5 `src/charts/*` Plotly · #6 `main.jsx` boot + `npm run build` + E2E (vite proxy → flask) ·
#7 deploy image · #8 delete `dashboard/` (relocate seam/format/registries to `webapi/`), update docs/memory.
