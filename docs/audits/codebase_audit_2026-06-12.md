# Full Codebase Audit — 2026-06-12

> ⚠️ **HISTORICAL — SUPERSEDED.** Point-in-time audit report. Its fix campaign
> already merged (see the `CHANGELOG`), and it was re-audited in PRs #124/#125/#126.
> Kept for provenance only — notably the **5 refuted false-positives** below, which
> exist nowhere else. Paths/structure here describe the 2026-06-12 tree (e.g. the
> pre-split `webapi/seam.py`, the `frontend/src/proto/` dir later renamed to
> `frontend/src/ui/`) and are **frozen** — do not treat them as current. Moved from
> `PLANS/` to `docs/audits/` because it is a historical report, not a feature plan.

Two-phase audit: (1) automated metrics pass (radon/ruff/pytest-cov), (2) manual
deep-review sweep by 12 area reviewers, with every finding adversarially
verified by an independent reviewer that read the code and tried to refute it.
Only confirmed findings are listed. 111 raw findings -> 106 confirmed, 5 refuted.
Severities below are the verifier-corrected ones. Some findings were
independently discovered by two areas (e.g. seam + frontend); duplicates are
kept as cross-confirmation.

## Phase 1 — Automated summary

- 497 tests pass; total coverage 81%; ruff + format clean; avg CC B (8.2).
- Risk concentration: `webapi/seam.py` (MI B 14.19, 7 functions grade C, 24%
  coverage, Halstead effort 3x the next file) and `webapi/format.py` (21%).
- Grade-C functions outside seam: `cli.ingest_reconcile` C12,
  `comtrade/pipeline.run` C13, `comex/pipeline.run` C11,
  `serving/curation.record_flow_market` C12.

## Phase 2 — Confirmed findings


### Severity: high

#### 1994 val_yearfx_usd is ~3 orders of magnitude wrong: year-average FX mixes CR$ and R$ across the July 1994 changeover

- **Where**: `dbt/models/gold/gold_pevs_production.sql`:222
- **Category**: bug · **Area**: dbt-silver-gold

fx_year averages the daily PTAX over the whole calendar year, and the pre-1994 guard is `reference_year >= 1994`, which INCLUDES 1994. The model's own premise (line 218: 'the FX rate of the year is in the currency-of-the-year (Cz$/USD etc.)') means SGS series 1 values for Jan-Jun 1994 are in Cruzeiros Reais (~CR$ 450-2750/USD) while Jul-Dec are in R$ (~0.85/USD). BCB_START_YEAR=1980 (.env.example:120, config.py:133), so silver_currency carries the full 1994 series, and brl_per_usd_avg for 1994 comes out in the hundreds instead of ~0.64. val_yearfx_usd for reference_year=1994 (PEVS covers 1986+) is therefore silently ~1000x too small. No test catches it: assert_pre1994_real_per_unit_bounded only checks `reference_year < 1994` and only the val_real_* columns. The same `>= 1994` guard + whole-year average pattern is copied into gold_pam_production.sql:182-185 (dormant only because PAM_START_YEAR defaults to 2010 — the env comment explicitly allows lowering it to 1994). Fix: guard with `>= 1995`, or restrict the 1994 average to dates >= 1994-07-01.

#### exportCoefficient byUf rows are never decorated with col/row — the 'Orientação exportadora' UF tile map renders broken

- **Where**: `frontend/src/data/producers.js`:103
- **Category**: bug · **Area**: frontend-data-charts

The export-coefficient view feeds data.byUf straight into BrazilTileMap, which positions each tile at d.col/d.row. The backend deliberately omits col/row (client-side registry join), and producers.js decorates them for productivityData (decorateUfRows(data.byUF)) and for snapshot ufData (decorateSnapshot) — but NOT for exportCoefficient (plain crossAnalytic passthrough). seam.export_coefficient by_uf rows carry only uf/name/region/production/exportV/coefPct, so every tile computes x = undefined * 64 = NaN and the 27-UF map renders garbage/blank for all commodities.

#### Implicit price (Preço médio implícito) is 1000× overstated for volume-family products — view hardcodes q×1e3 while the serializer scales volume q by 1e6

- **Where**: `frontend/src/proto/ViewProductProfile.jsx`:94
- **Category**: bug · **Area**: frontend-data-charts

serializers._product_ts emits q in mil t for mass (native/1e3) but mi m³ for volume (native/1e6). ViewProductProfile correctly uses a family-aware multiplier for the quantity series (massQtyMul=1e3 / volumeQtyMul=1e6) but the implicit-price math divides by `d.q * 1e3` for BOTH families. For mass that recovers native tonnes (correct); for volume it yields native_m³/1e3, inflating the displayed R$/m³ (or US$/m³) price by 1000×. PEVS's dominant products (madeira em tora, lenha, carvão) are volume family, so the 'Preço médio implícito' KPI and chart show prices three orders of magnitude too high on the default banco.

#### Geography 'ano × UF' heatmap fabricates per-UF history by scaling each UF's single total with the national time profile

- **Where**: `frontend/src/proto/ViewGeography.jsx`:65
- **Category**: data-quality · **Area**: frontend-data-charts

The snapshot's ufData has no year grain (one row per UF), yet ViewGeography renders a 'Evolução temporal · ano × UF' heatmap. It synthesizes each UF's yearly values as ufTotal × (nationalYearValue / nationalMax) — i.e., every UF gets the identical national curve, just rescaled. This is a synthetic-prototype construction now presented to Embrapa researchers as real Gold per-UF history (no 'demonstração' banner, real banco label). Any real divergence between UFs over time is invisible/false.

#### Implied price is 1000x too high for volume-family products (family-blind q*1e3)

- **Where**: `frontend/src/proto/ViewProductProfile.jsx`:94
- **Category**: bug · **Area**: frontend-proto-ui

productTS.q arrives in 'mil t' for mass but 'mi m³' for volume (serializer q_scale = 1e3 vs 1e6). The implied-price math divides by d.q*1e3 regardless of family, which is correct only for mass. For volume products (Madeira em tora, Lenha — the largest PEVS products) the 'Preço médio implícito' KPI, the price chart and the spark show prices 1000x too high (e.g. R$ 140/m³ renders as R$ 140.000/m³). The same component scales the quantity series correctly with the family-aware qtyMul (line 78), so the view contradicts itself. csvExport.js:73 has the same family-blind Math.round(d.q*1e3), so the exported 'quantidade' column mixes t (mass rows) with mil m³ (volume rows) under one unitless header.

#### Display-currency reset on banco switch (changeDatabase) was never ported — USD trade values rendered as R$ / via mock FX rates

- **Where**: `frontend/src/main.jsx`:295
- **Category**: bug · **Area**: frontend-proto-ui

bancos.js and MetricConventions.jsx both document that 'changeDatabase resets the DISPLAY currency to baseCurrency', but no such function/effect exists in the React entry — clicking a banco only calls setDatabase. The backend always serves trade bancos in USD (seam.py: _TRADE → val_yearfx_usd) regardless of the requested currency. So on the default flow (app loads with conventions BRL·IPCA, user clicks MDIC COMEX): plain-convFactor paths (ViewValueVolume value series/stacks, ViewOverview 'Valor total' KPI via formatValue, ViewProductCompare, csvExport's `valor_BRL` column) display the raw USD numbers under R$ labels (≈5x understated), while base-aware paths (ViewOverview UF map, ViewGeography via convFactorFor) multiply by a hardcoded mock rate 1/0.205≈4.88 — so the same screen shows two inconsistent magnitudes, and the 'BRL' figures rest on a frozen fake FX rate (CURRENCY_FX 0.205/0.187) in a scientific dashboard.

#### Filter summary leaks across banco switches — stale product basket silently zeroes every chart

- **Where**: `frontend/src/main.jsx`:343
- **Category**: bug · **Area**: frontend-proto-ui

The single `summary` state is never reset when the banco changes (AppShell.onBanco only calls setDatabase). FilterMenu.onApply always emits a concrete basket array (even a no-op 'Aplicar' on all products), so after any apply on PEVS, switching to COMEX intersects PEVS codes with the COMEX product universe: selectedProducts = [] → ts all zeros, productTS {}, productShare = 0 → ufData/regions scaled to 0 — the entire dashboard renders empty/zero with no error. Worse, withChips short-circuits when the summary already carries chip strings (`if (s.products && s.period) return s`), so the trigger bar keeps showing the PREVIOUS banco's chips (e.g. 'Castanha-do-pará', PEVS year range) over the new banco's blank charts.

#### comtrade_cpc_value sums append-only Bronze with no dedup — values inflate with every re-ingestion

- **Where**: `src/embrapa_commodities/serving/sql.py`:486
- **Category**: data-quality · **Area**: serving-layer

comtrade_cpc_value() reads the COMTRADE Bronze table directly and does sum(safe_cast(primaryValue as float64)) grouped by (customsCode, flowCode, refYear), with only two predicates: customsCode != 'C00' and customsCode is not null. Bronze is append-only with explicitly at-least-once load semantics: the pipeline always re-fetches the latest year and reloads any changed chunk, and a crash between load and the bronze-loaded marker reloads the whole chunk — its own docstring says 'Duplicate rows are expected and safe: Silver dedupes on the natural key by ingestion_timestamp desc' (src/embrapa_commodities/comtrade/pipeline.py:294-297). But this query bypasses Silver and applies NO dedup: no qualify row_number() over the natural key by ingestion_timestamp desc, no collapse of the duplicate-qtyUnitCode rows that carry an IDENTICAL primaryValue (the exact double-count bug commit #102 fixed in silver_comtrade_flows.sql:62-68), no partnerCode != '0' (World aggregate) exclusion, and no HS6/length(cmdCode)=6 filter (all applied in Silver, dbt/models/silver/silver_comtrade_flows.sql:47-69). Consequence: the values served by gateway.fetch_comtrade_cpc_value (gateway.py:395) and displayed as absolute US$ bi in the market-nature analysis and as real cell values in the Curadoria regime×flow worklist (webapi/seam.py:816,872-881) multiply by the number of times each chunk was loaded into Bronze — wrong numbers shown to researchers, growing worse over time.

#### seam.py analytical core has zero test coverage (2 of 23 public functions tested)

- **Where**: `tests/test_webapi_seam.py`:1
- **Category**: test-gap · **Area**: tests-quality

test_webapi_seam.py contains only 5 tests covering 2 functions (flow_market_worklist, market_nature) of the 23 public functions in src/embrapa_commodities/webapi/seam.py (894 lines). Untested functions perform the scientific unit math the dashboard exists for: snapshot() + _with_overview_quantities() (family-aware q_mass/q_vol aggregation and the COMEX total_value_usd→total_value rename), effective_value_column() (the currency×correction fallback chain that silently swaps a user's requested deflated column for BRL), cross_series()/_cross_points() (÷1e9 / ÷1e6 / ÷1e3 display scaling and the derived exp_price), market_share(), export_coefficient() (kg→mil t coefficients), price_spread() (gate price = v/(q*1000) US$/kg), trade_mirror() (discrepancy %), value_added() (premium = price_p/price_b), curation_worklist(), curator_emails(), productivity(), flow_data(), partner_data(), monthly_data(), cross_common_window() (inverted-interval fallback). A unit/scale regression in any of these (e.g. _cross_points' `wmap.get(year) or 1` silently turning a missing-weight year's 'US$/kg price' into the raw total value) would ship to researchers with no test failing, while the suite LOOKS like it covers webapi (3 webapi test files exist).

#### Trade-banco quantities (COMEX/COMTRADE) serialized 1000x too large: kg-native qty summed and scaled as if tonnes

- **Where**: `src/embrapa_commodities/webapi/seam.py`:168
- **Category**: bug · **Area**: webapi-seam

snapshot() for trade bancos builds overviewTS q_mass by summing product_ts total_qty_native per family (seam._with_overview_quantities), and the serializer scales massa by /1e3 assuming the native unit is tonnes ('t->mil t') and emits per-product q the same way. That assumption only holds for PEVS/PAM (unit_native = Toneladas). For COMEX/COMTRADE, qty_native is the source statistical quantity, predominantly kilograms (COMEX 'QUILOGRAMA LIQUIDO', COMTRADE unit code 8 = kg), so the Overview KPI 'Quantidade (massa)' and Valor-e-Volume mass series for trade bancos are displayed ~1000x too large (kg/1e3 = t, labeled 'mil t' per contracts.js:48). Worse, the family-level sum mixes NCMs whose native unit is kg with NCMs in 'TONELADA METRICA LIQUIDA' (both family=massa), an apples+oranges sum; qty_base (already converted to t) exists in the marts and is what should be summed. The cross-series path got this right (exp_weight kg/1e6 -> mil t in _cross_points), proving the snapshot path is an oversight, not a convention.

#### productTS/overview quantities treat qty_native as t/m³ — COMEX/COMTRADE mass quantities off by 1000× (or worse) and summed across incompatible units

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:216
- **Category**: bug · **Area**: webapi-serializers

_product_ts divides total_qty_native by 1e3 for family 'massa' (comment: 't→mil t') and _overview_ts divides q_mass by 1e3, but the seam feeds qty_native, which is in the SOURCE's native unit, not the family base unit. For PEVS/PAM native=t so it works; for COMEX the NCM statistical unit is mostly QUILOGRAMA LIQUIDO (kg), sometimes TONELADA METRICA LIQUIDA (t), GRAMA LIQUIDO (g) or QUILATE — and for COMTRADE mass qty is kg. The frontend treats q as 'mil t' (ViewValueVolume.jsx:18 'd.q_mass : mil t', ViewProductProfile scales with massQtyMul), so a kg-native NCM displays 1000× too large (a grama-native one 10⁶×). Worse, seam._with_overview_quantities sums qty_native ACROSS products of family 'massa', adding kg-NCMs to t-NCMs into one q_mass — a unit-incoherent number rendered as real data in the 'Valor e volume' view. The marts carry qty_base (normalized to t/m³) precisely for this, but it is never used for productTS/overview.

#### _FLAG_KEY uses the prototype's synthetic flag taxonomy — real Gold flags INCOMPLETE and MISSING_WEIGHT are silently dropped from quality charts

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:35
- **Category**: bug · **Area**: webapi-serializers

Gold's actual data_quality_flag enum is OK/MISSING_VALUE/MISSING_QUANTITY/INCOMPLETE (PEVS/PAM/COMTRADE) and OK/MISSING_VALUE/MISSING_WEIGHT/INCOMPLETE (COMEX). _FLAG_KEY instead maps ESTIMATED/OUTLIER/BOUNDARY_HISTORIC — flags no Gold table ever emits — and omits INCOMPLETE and MISSING_WEIGHT. In _quality_ts, unmapped flags are counted in `total` but mapped to no output key, so the per-year stack silently loses those shares (never sums to 1); for COMEX every MISSING_WEIGHT row vanishes from the quality-over-time chart. _quality_by_product emits only the six _FLAG_KEY columns while inflating the denominator with the dropped flags. The donut (_quality) passes the raw id through, and since frontend QUALITY_FLAGS (data.js:299) also lacks INCOMPLETE/MISSING_WEIGHT, decorate.js falls back to showing the raw English id ('INCOMPLETE') as a user-facing label — violating the pt-BR rule. tests/test_webapi_serializers.py:162 codifies the wrong taxonomy (BOUNDARY_HISTORIC), confirming it was ported from the prototype, not from Gold.

#### serialize_export_coef byUf rows lack the contracted col/row tile coords and nothing decorates them — the export-coefficient tile map renders broken

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:387
- **Category**: bug · **Area**: webapi-serializers

The ExportCoefficient contract requires byUf rows with col/row (contracts.js:114). serialize_export_coef passes seam rows through with only uf/name/region/production/exportV/coefPct, and the frontend producer for export-coef (producers.js crossAnalytic) returns the API payload as-is — unlike productivityData, which explicitly calls decorateUfRows. ViewExportCoef feeds these rows straight into BrazilTileMap, which positions each tile at d.col*(CELL_W+GAP) — undefined col/row yields NaN coordinates, so the 'Coeficiente de exportação' choropleth (a live view) renders with all tiles collapsed/invisible. The serializers module docstring claims 'The JS data layer decorates the rows we emit (keyed by uf)', but that decoration only exists for snapshot.ufData and productivity byUF.


### Severity: medium

#### Partial/failed Gold backup still satisfies doctor's freshness check (no completeness marker)

- **Where**: `src/embrapa_commodities/backup.py`:78
- **Category**: bug · **Area**: app-infra-python

backup.run() extracts Gold tables sequentially and raises on the first failed extract_job.result(), leaving an incomplete backups/run=<ts>/ prefix containing only the tables exported before the failure. No manifest or success marker is written. doctor._check_backup_freshness derives freshness solely from the run=<ts>/ prefix timestamps, so a crashed half-backup is indistinguishable from a complete snapshot — the operator sees 'latest=<ts> (0d ago)' and believes the cold-storage rollback path is intact while most Gold tables are missing from it.

#### .env.example says GCP_IMPERSONATION_SA accepts a short name, but the runtime passes it verbatim and breaks

- **Where**: `.env.example`:26
- **Category**: doc-mismatch · **Area**: app-infra-python

The .env.example comment states the var 'Accepts either a short name (e.g. `sa-secret-reader-prod`) or a full email', but only scripts/setup_dev_env.py expands short names (line 260) when generating dbt profiles. The Python runtime (config.get_credentials) hands the value verbatim to impersonated_credentials as target_principal, so a user who follows the documented short-name form breaks every ingest, doctor BQ/GCS check, and backup with an opaque impersonation error. config.py's own field description ('SA email to impersonate') contradicts .env.example.

#### webapi deploy env allowlist silently drops CURATION_ALLOWED_EMAILS — documented curation write lockdown never reaches prod

- **Where**: `deploy/webapi/deploy.sh`:78
- **Category**: security · **Area**: cross-cutting-infra

The Cloud Run deploy forwards runtime env via an explicit allowlist that omits CURATION_ALLOWED_EMAILS, even though the deployed webapi reads it for write authorization (routes.py builds the curator allowlist from Settings.curation_allowed_emails). .env.example and docs/operations_runbook.md both present this env var as the way to restrict who may POST curation edits ('Set it once researchers are onboarded to lock writes down'). An operator who sets it in .env and runs `make webapi-deploy` gets NO lockdown: the var never reaches the service, and since empty allowlist = open mode, any IAP-authenticated caller can still write curation rows — silently. BQ_MAX_BYTES_BILLED (the documented serving-path cost ceiling) is likewise consumed by gateway.run_query but not forwarded, so a tuned ceiling in .env never applies in prod.

#### IAP_AUDIENCE is consumed but documented nowhere — the 'fails closed' IAP JWT verification is off by default and undiscoverable

- **Where**: `src/embrapa_commodities/config.py`:236
- **Category**: security · **Area**: cross-cutting-infra

The signed X-Goog-IAP-JWT-Assertion is only verified when Settings.iap_audience is set (iap.py:134 `if audience: return verify_iap_jwt(...)`); otherwise the curation author comes from the spoofable plaintext X-Goog-Authenticated-User-Email header. docs/auth_architecture.md asserts the app 'additionally validates the signed X-Goog-IAP-JWT-Assertion so a misconfiguration (e.g. an accidental public ingress) fails closed' — but never mentions that this requires IAP_AUDIENCE, and the variable appears in no documentation at all: .env.example has the curation/cache section but no IAP_AUDIENCE entry. The only occurrence outside src/ is the deploy.sh allowlist regex. An operator following .env.example + auth_architecture.md deploys prod with the JWT check disabled while the doc claims it is active.

#### README/ARCHITECTURE/.env.example/dbt comments still present the removed Dash UI as the current dashboard ('UI under reconstruction')

- **Where**: `README.md`:47
- **Category**: doc-mismatch · **Area**: cross-cutting-infra

The 2026-06 Dash→React migration shipped (deploy/webapi/, src/embrapa_commodities/webapi/, frontend/ — per CLAUDE.md the React SPA is 'live on Cloud Run'), yet the primary docs still describe the dashboard as a Dash app being rebuilt: README calls the consumption path 'Dash dashboard @ Cloud Run ... UI under reconstruction' and its diagram says 'Dashboard Dash @ Cloud Run'; ARCHITECTURE.md says the UI is 'currently being rebuilt with the Claude Design System' and that sa-web-dashboard-prod 'is dormant while the UI is rebuilt'; .env.example and dbt_project.yml reference 'the stateless Dash app'; docs/testing.md says 'Frontend under reconstruction ... will bring its own testing strategy' although frontend Vitest tests already run in ci.yml; docs/frontend_data_contract.md says 'the Dash UI still arrives with the design-system handoff'; deploy/ingestion/Dockerfile says the dashboard Service image 'arrives with the Claude Design System handoff'; deploy/webapi/Dockerfile references the nonexistent module `embrapa_commodities.dashboard.seam` (it is webapi/seam.py). These claims send readers to a UI that no longer exists and hide the one that does.

#### Scheduled/auto prod dbt builds never pass enable_curation — SCD2 view code changes and tests are unpropagated once curation is activated

- **Where**: `.github/workflows/dbt-build-prod.yml`:213
- **Category**: inconsistency · **Area**: cross-cutting-infra

dim_commodity_scd2 and dim_code_industrialization_scd2 are gated by `enabled=var('enable_curation', false)`. The dbt-build-prod workflow — whose stated purpose is 'the bridge between PR merged ... and the physical tables reflect that code' — always runs plain `dbt build --target prod`, so after the documented one-time prod activation, any merged change to the two SCD2 models is silently skipped by every push-triggered and daily scheduled build (the views drift from main), and their schema tests never run in CI or on the schedule. There is also no tooling path for the prod activation itself: `make dbt-build-curation` builds dev only (no --target prod), and `make reconcile`'s chained prod build (Makefile:44) also omits the var.

#### ARCHITECTURE.md folder structure and README sources/CLI omit the shipped webapi, frontend, deploy and PAM artifacts

- **Where**: `ARCHITECTURE.md`:150
- **Category**: doc-mismatch · **Area**: cross-cutting-infra

The 'Folder Structure' tree in ARCHITECTURE.md predates both the React migration and the PAM source: it lists no src/embrapa_commodities/webapi/, no frontend/, no deploy/ directory at all; the dbt listings omit silver_ibge_pam.sql, gold_pam_production.sql, gold_commodity_crosswalk is listed but serving_pam_annual.sql and dim_code_industrialization_scd2.sql are missing; the .github/workflows list shows only ci.yml and dbt-build-prod.yml (dbt-source-freshness.yml and gitleaks.yml exist); docs/ listing omits gold_data_model.md and operations_runbook.md. README likewise: the pipeline diagram and 'Sources today' omit IBGE PAM / gold_pam_production, and the CLI reference omits `ingest ibge-pam`, `ingest ibge-batch`, `ingest reconcile`, `doctor`, `backup-gold`, `monitor` — all existing commands. Readers using these as the map will not find major shipped components.

#### CONTRIBUTING.md instructs 'Docstrings in Portuguese', the inverse of the project language rule and actual practice

- **Where**: `CONTRIBUTING.md`:198
- **Category**: inconsistency · **Area**: cross-cutting-infra

The project language rule (CLAUDE.md Code Style) is explicit: text read exclusively by the development team — identifiers, docstrings, comments — is English; only end-user-visible strings are Portuguese. CONTRIBUTING.md tells contributors the opposite ('Docstrings in Portuguese — technical comments may be in English'), and the codebase itself uses English docstrings throughout (config.py, iap.py, app.py, etc.). A contributor following CONTRIBUTING.md would introduce systematic violations of the convention.

#### PAM crosswalk join is structurally dead; documented activation path ('seed pam rows') cannot work

- **Where**: `dbt/models/serving/serving_pam_annual.sql`:98
- **Category**: doc-mismatch · **Area**: dbt-serving-core

serving_pam_annual LEFT JOINs gold_commodity_crosswalk on x.source = 'pam' and its comment claims commodity linkage 'lights up if pam rows are seeded'. That is impossible: (1) gold_commodity_crosswalk only expands seed prefixes against codes harvested from gold_pevs_production / gold_comex_flows / gold_comtrade_flows — its source_codes CTE never scans gold_pam_production, so a (source='pam', code) row can never be emitted; (2) the seed schema test rejects 'pam' outright (accepted_values [pevs, comex, comtrade] on commodity_crosswalk.source), as does the accepted_values test on the crosswalk model itself (_gold.yml:373-377). Consequence: commodity_id/commodity_name are permanently NULL for PAM, and a developer following the in-code instruction will either fail the seed test or silently get no rows, with no hint that gold_commodity_crosswalk.sql also needs changing.

#### productTS sums qty_native across unit families, defeating the family split the marts were built to enforce

- **Where**: `src/embrapa_commodities/serving/sql.py`:609
- **Category**: bug · **Area**: dbt-serving-core

The serving marts deliberately put `family` in the grain so quantities are only ever summed WITHIN one physical-unit family (mart comment: 'qty_base summed WITHIN a family ... correctly splits the rare mixed-unit NCM'), and _serving.yml:79-83 confirms a real mixed-unit NCM exists in prod (the uniqueness test 'FALSELY failed on exactly that NCM' until family was added to the tested key). But the BFF reader product_timeseries() groups only by (code, reference_year) and computes sum(qty_native) with any_value(family) — for that mixed-unit NCM it adds quantities expressed in two different statistical units into one number, then serializers._product_ts (webapi/serializers.py:216) picks the t-vs-m³ display scale from whichever family any_value happened to return. The productTS quantity chart for such a code is wrong in value and possibly in unit/scale. products() (sql.py:571-586) has the same any_value(family)/any_value(unit_native) arbitrariness.

#### gold_comtrade_flows has no pre-1994 (old-currency) guard on its BRL conversion, unlike the PEVS/PAM golds

- **Where**: `dbt/models/gold/gold_comtrade_flows.sql`:154
- **Category**: bug · **Area**: dbt-silver-gold

val_nominal_brl and all val_real_* columns multiply the source USD by fx_year's brl_per_usd_avg with NO year guard. For any year 1984-1993 (when PTAX series 1 exists but is denominated in Cz$/NCz$/Cr$/CR$ per the project's own convention), the 'BRL' output would be in old-currency units, off by 10^3-10^9, and val_real_* would propagate the garbage. gold_pevs_production explicitly nulls foreign-FX columns pre-1994 for exactly this reason; this model omits the guard. Latent today only because the COMTRADE window is intentionally capped at 2022-2023, but the model's own YAML range test permits 1960+ (`between 1960 and extract(year from current_date()) + 1`, _gold.yml:297-299) and the partition range starts at 1960 — so the first historical backfill silently produces corrupted BRL/real columns with no failing test.

#### Latest-wins dedup cannot drop rows DELETED from a revised COMEX/COMTRADE source file — phantom flows persist forever

- **Where**: `dbt/models/silver/silver_comex_flows.sql`:26
- **Category**: data-quality · **Area**: dbt-silver-gold

COMEX re-ingests a whole (flow, year) file when its ETag changes, appending every row of the NEW file to append-only Bronze. The qualify keeps the latest ingestion per natural key — which handles UPDATED rows, but a row that MDIC removes in the restated file (a retracted/zeroed flow) has no newer Bronze version, so the stale row survives dedup and stays in Silver/Gold indefinitely. Neither the nightly ETag delta nor the monthly `reconcile` fixes it (both only append). The same applies to silver_comtrade_flows full re-downloads. Because the source semantic is whole-file replacement, Silver should scope each (flow, year) to rows from that file's latest ingestion batch (e.g. keep only rows whose ingestion_timestamp equals the max per (flow, CO_ANO)) rather than per-row latest-wins. Consequence: totals for restated periods can overstate, with no test able to detect it (the grain stays unique).

#### Conventions change never re-triggers snapshot load — deep-linked ?cur/?corr wedges all data views on the loading skeleton

- **Where**: `frontend/src/data/dataStore.js`:237
- **Category**: bug · **Area**: frontend-data-charts

dataStore caches snapshots per `${id}|${currency}|${correction}` and setConventions() only swaps activeConv + notify()s, relying (per its own comment) on DataBoundary re-render to 'call load(id)'. But useBancoData only calls load() inside a useEffect keyed [bancoId] — re-renders never re-issue load. On mount, the child (DataGate) effect runs load() with the module default {BRL, IPCA} BEFORE the parent Dashboard effect applies the URL-hydrated conventions; the subsequent setConventions switches the cache key to e.g. `ibge_pevs|USD|IPCA`, which nothing ever loads. status() returns 'idle' forever and DataGate renders <DataLoading/> indefinitely (the 12s freshness tick just re-reads the same idle state). Any shared/bookmarked URL with a non-default currency or correction (?cur=USD, ?corr=Nominal — exactly what the URL write-back in main.jsx emits) permanently blanks every per-banco data view; recovery requires switching banco and back.

#### Basket filter fakes per-UF narrowing with a uniform product-count share (selected/all) instead of the real per-product split

- **Where**: `frontend/src/proto/dataFilters.js`:121
- **Category**: data-quality · **Area**: frontend-data-charts

applyFilters scales every UF total (value, q_mass, q_vol) by productShare = selectedProducts.length / allProducts.length when a basket is applied. Picking the 2 smallest of 12 products keeps 2/12 ≈ 17% of EVERY UF's total — regardless of what those products actually represent or where they're produced. Region totals and the choropleth/tile map inherit this fabricated distribution. The backend already proved the real join is feasible (/api/product-uf exists for ViewProductProfile); the geography view still serves the synthetic-era heuristic on live data.

#### Active filters are silently dropped on Fluxos/Parceiros/Sazonalidade/Produtividade — views pass summary, producers and routes discard it

- **Where**: `frontend/src/data/producers.js`:146
- **Category**: bug · **Area**: frontend-data-charts

ViewFlows/ViewPartners/ViewSeasonality/ViewProductivity call the producers with the active filter summary (basket, startDate/endDate), matching the contract signatures (flowData(bancoId, summary), productivityData(bancoId, crop, summary)). The API-backed producers accept only bancoId(/crop) and ignore summary entirely; the Flask routes likewise parse no filter params and pass summary=None to the seam — even though seam.flow_data/partner_data/monthly_data DO support year+basket filtering. Meanwhile the FilterTriggerBar still renders period/product chips on these views, so a researcher who applies a year window or basket sees unchanged charts that claim to be filtered.

#### serialize_monthly returns monthlyAvg: [] on empty data, violating the 12-value contract and crashing ViewSeasonality

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:480
- **Category**: bug · **Area**: frontend-data-charts

contracts.js defines MonthlyData.monthlyAvg as '12 values', and producers.js deliberately ships 12 zeros in the loading shell so 'the view's peak/low/amplitude math survives'. But when /api/monthly resolves with an empty frame, serialize_monthly emits monthlyAvg: [] — then ViewSeasonality computes peakIdx = [].indexOf(Math.max(...[])) = -1, reads monthlyAvg[-1] = undefined, and fmt(undefined) throws TypeError on .toLocaleString, sending the whole perspective to the error boundary ('Erro ao renderizar a perspectiva') instead of an honest empty state. The Cobertura KPI also renders 'undefined–undefined'.

#### Backend 'incompatible' flag (export-coef / price-spread honest refusal) is never consumed by the frontend — volume commodities show blank charts with no explanation

- **Where**: `frontend/src/proto/ViewsMultiSource.jsx`:46
- **Category**: inconsistency · **Area**: frontend-data-charts

seam.export_coefficient and seam.price_spread deliberately refuse non-mass selections (volume m³ or mixed baskets) and serialize_export_coef/serialize_price_spread propagate `incompatible: true` so the UI can explain why. No frontend code reads the flag (grep finds it only in backend files); producers' shells omit it and the views have no incompatible branch. Selecting a volume commodity (e.g. madeira) in 'Orientação exportadora' or 'Spread de preço' yields '—%' KPIs and empty charts with zero explanation, defeating the server's designed honesty.

#### Snapshot ufData q_mass/q_vol are hardcoded 0.0 while the contract declares them real — Geografia quantity dimensions render an all-zero map

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:260
- **Category**: data-quality · **Area**: frontend-data-charts

_uf_data emits q_mass: 0.0 and q_vol: 0.0 for every UF (acknowledged server-side as a known gap), but contracts.js BancoSnapshot declares ufData rows with real q_mass/q_vol, and ViewGeography offers 'Quantidade (massa)' / 'Quantidade (volume)' dimensions whenever the basket has those families — gated on families present, not on data availability. Selecting them shows an all-gray/zero choropleth, zero region bars, and a zero heatmap, with no in-product notice that per-UF quantity is unavailable.

#### MetricConventions strip is dead code — no UI path can change currency/correction, though FilterMenu tells users to use it

- **Where**: `frontend/src/proto/MetricConventions.jsx`:296
- **Category**: dead-code · **Area**: frontend-data-charts

The MetricConventions component (the 'Convenções métricas' strip — currency, inflation correction, display units) is imported for its window helpers but never rendered: Dashboard never passes its setConventions state setter to AppShell/MainScreen, and no JSX anywhere instantiates window.MetricConventions. The entire server-side currency×correction column selection (/api/snapshot currency/correction params, the project's 'scientific core') is unreachable except by hand-editing the URL — which then triggers the load deadlock (separate finding). FilterMenu actively points users to this non-existent UI ('a moeda e correção de exibição são definidas em Convenções métricas').

#### Saúde page charts SYNTHETIC quality series as real 'IBGE PEVS' history

- **Where**: `frontend/src/proto/ViewHealth.jsx`:355
- **Category**: data-quality · **Area**: frontend-proto-ui

The 'Qualidade dos dados · histórico' card titled '% de linhas íntegras (flag = OK) · IBGE PEVS' plots window.QUALITY_TS — the synthetic prototype series generated in data.js (0.71→0.89 with sine noise) — not the real snapshot qualityTs the same file already uses for alert derivation (line 68-75). The 'Bancos saudáveis' KPI sparkline (line 162) does the same. This directly contradicts the page's own contract ('Every fact here is read from the LIVE backend seam… instead of inventing') and shows researchers fabricated quality telemetry on an institutional health page.

#### Geography 'ano × UF' heatmap fabricates per-UF time evolution from the national curve

- **Where**: `frontend/src/proto/ViewGeography.jsx`:75
- **Category**: data-quality · **Area**: frontend-proto-ui

The 'Evolução temporal · Mapa de calor · ano × UF' chart has no real per-UF×year data: each UF's yearly values are computed as UF_current_value × (national ts value of that year ÷ max) — every UF gets the identical normalized national trajectory. With real Gold data now feeding the view, this presents invented temporal evolution per state as real history, with no preview/'modelado' label. Also mixes dimensions: the shape always comes from the VALUE series (t.v) even when the selected metric is mass/volume.

#### Product filter fabricates geographic split: ufData/regionData scaled by uniform count-share

- **Where**: `frontend/src/proto/dataFilters.js`:121
- **Category**: data-quality · **Area**: frontend-proto-ui

When a product basket is active, per-UF and per-region values are not re-queried; every UF's value/q_mass/q_vol is multiplied by productShare = selectedCount/totalCount. Filtering to 1 of 3 PEVS products scales all 27 UFs by 1/3 uniformly — rankings never change and the displayed 'filtered' magnitudes are invented (a product concentrated in PA shows the same share in RS). These fabricated values feed ViewGeography, ViewOverview's UF map, and are exported as real numbers by csvExport (cases 'geo' and 'concentration'). The real per-product×UF endpoint exists (/api/product-uf, used by ViewProductProfile) but isn't used here.

#### Geography mass/volume metric toggles render all-zero maps on live data (per-UF quantities are always 0)

- **Where**: `frontend/src/proto/ViewGeography.jsx`:34
- **Category**: bug · **Area**: frontend-proto-ui

The backend serializer ships q_mass = 0.0 and q_vol = 0.0 for every UF row ('known gap: production_by_uf returns only total_value'), but ViewGeography still offers the 'Quantidade (massa)' and 'Quantidade (volume)' metric buttons whenever those families exist in the basket. Selecting them shows an all-zero choropleth/tile map, zero heatmap and zero Top-10 ranking with no explanation — looking like a data outage rather than an unwired dimension. The dims' `available` flag checks basket families, never data presence.

#### Stale 'valores ilustrativos' captions on charts that now show real API data

- **Where**: `frontend/src/proto/ViewsMultiSource.jsx`:71
- **Category**: inconsistency · **Area**: frontend-proto-ui

Four chart captions hardcode 'valores ilustrativos' (illustrative values) from the synthetic-prototype era, but the data underneath is now real: ViewExportCoef's national-coefficient line (fed by /api/cross/export-coef), ViewMirror's three-source chart (/api/cross/mirror), ViewFlows' Sankey (/api/flow) and ViewSeasonality's month×year heatmap (/api/monthly) for live COMEX. The PreviewBanner correctly renders only when data.preview, but these captions are unconditional — telling researchers real Gold/COMTRADE data is fake. ViewExportCoef's caption also hardcodes '1997–2024' regardless of the actual series window.

#### Value-range filter is a no-op: UI promises row exclusion but no data path applies it

- **Where**: `frontend/src/proto/FilterMenu.jsx`:807
- **Category**: bug · **Area**: frontend-proto-ui

FilterMenu's value section tells the user 'Inclua apenas linhas cujo valor monetário esteja dentro da faixa', the applied range shows as an active chip, and it round-trips through the share URL — but nothing consumes it: /api/snapshot receives only banco+currency+correction, and dataFilters.js uses valueMin/valueMax solely in valueShareForRange, which now returns 1.00 for every threshold (presets and custom). Setting '≥ R$ 1 mi' changes no chart, no KPI, no CSV export, while the chip claims the filter is active — a silent contract gap that can mislead research conclusions.

#### Comtrade reference fetches documented as retryable are never retried; one blip aborts the whole run

- **Where**: `src/embrapa_commodities/comtrade/client.py`:113
- **Category**: bug · **Area**: ingestion-comex-comtrade

list_reporters() and list_hs6_codes() call core_http.get_drained directly with no @http_retry_policy decorator, and get_drained performs a single GET with no retry. Yet the code's own contract says these failures are retried: ComtradeTransientError is documented as 'Transient (retryable) error: 5xx/408 (incl. short reference-file hiccups)' (client.py:69), ComtradeQuotaError's docstring says 'a 429 on the public, key-less reference files (list_reporters / list_hs6_codes) is a momentary rate limit and stays transient/retryable' (client.py:82-84), and list_hs6_codes says 'an empty reference is treated as a transient fetch failure' implying a retry (client.py:158-160). In reality nothing catches or retries these. Consequence: pipeline.run() calls resolve_reporters(settings) before the chunk loop (pipeline.py:401) and the CLI does the same (cli.py:496), both outside any continue-on-failure handling — a single momentary 5xx/429/connection error on the Reporters reference crashes the entire `embrapa ingest comtrade` run before any chunk executes. A transient HS-reference blip inside resolve_cmd_codes fails chunks one by one instead of being retried. Only fetch_chunk (client.py:174-179) is actually wrapped in the retry policy.

#### BCB --full silently skips a misconfigured/empty series when any other series returns data

- **Where**: `src/embrapa_commodities/bcb/series.py`:115
- **Category**: bug · **Area**: ingestion-ibge-bcb

extract()'s docstring promises 'In full mode an empty fetch is a real failure → raises', and bcb/client.py relies on that to justify mapping 404 to empty ('A genuinely bad series code also 404s and yields empty here, which the full-mode no-data guard catches'). But the guard only fires when ALL configured series come back empty: a single typo'd code (e.g. BCB_CURRENCY_SERIES='1:USD,216190:EUR') is silently dropped via 'if df.empty: continue' even on `ingest --full` and the monthly automated `ingest reconcile`. The run reports success while one whole series is permanently absent from Bronze, and the downstream Gold val_yearfx_*/val_real_* columns for that label come out NULL with no error anywhere. doctor only validates the three inflation pivot codes against the config map, not against actual data, so FX or extra inflation series have no safety net.

#### IBGE/PAM --from-raw replays archives in lexical basename order, letting stale extracts win Silver dedup

- **Where**: `src/embrapa_commodities/ibge/pipeline.py`:139
- **Category**: bug · **Area**: ingestion-ibge-bcb

bronze_from_raw() replays every archived raw object returned by list_raw(), which sorts basenames lexically (core/raw.py:175). IBGE/PAM basenames encode products+year-window only (`products_<codes>_<start>_<end>`), NOT extraction time — unlike BCB, whose basenames are run-stamped so lexical order == chronological order. Each replayed object is stamped with a fresh `pd.Timestamp.now(tz="UTC")` at load time, and Silver dedupes by `ingestion_timestamp desc`. So after a mixed trail (e.g. an old `ibge-batch` backfill chunk grid like 1991_1995 plus a newer `--full` object 1986_2026, or chunk grids from different chunk_years), `ingest ibge --from-raw` replays the lexically-later but possibly older-fetched archives LAST, giving them the newest ingestion_timestamp — silently resurrecting stale readings into Silver/Gold for the overlapping years. The docstring's claim that 'overlapping windows collapse to the latest reading' is only true when lexical basename order happens to match fetch recency. Replay should order by the stored `fetched_at` provenance, not basename. Same defect duplicated in pam_pipeline.bronze_from_raw.

#### Curator allowlist table never auto-creates — runbook's setup path is broken

- **Where**: `src/embrapa_commodities/serving/curation.py`:93
- **Category**: doc-mismatch · **Area**: serving-layer

ensure_curators_table() has zero production callers — grep finds only a unit test (tests/test_serving.py:743) and the runbook reference. Unlike the three log tables (which self-heal inside each record_* writer, e.g. curation.py:209,354,459), nothing in the app factory, routes, seam, or gateway ever creates the curators table; fetch_curators (gateway.py:408) only reads it and raises NotFound, which seam.curator_emails() (webapi/seam.py:660) swallows as 'no allowlist'. docs/operations_runbook.md:40 tells the operator 'The table auto-creates on first use (serving.curation.ensure_curators_table)' — false. An operator following the runbook to enable the authorization allowlist hits 'table not found' on the documented INSERT, and until the table is created manually the curation gate stays at the permissive default (any IAP-authenticated caller may curate).

#### Settings fixtures in several test files don't isolate from the developer's .env (env-dependent flakiness)

- **Where**: `tests/test_serving.py`:479
- **Category**: inconsistency · **Area**: tests-quality

Settings has model_config env_file=".env" (config.py:38-40), and the documented setup (CLAUDE.md/README: `cp .env.example .env`) puts a real .env at repo root. Tests in test_serving.py, test_webapi_routes.py, test_doctor.py, test_bcb_pipeline.py, test_backup.py and test_gcp_* construct Settings WITHOUT `_env_file=None`, so any field not explicitly passed is read from the developer's .env / shell env. Several assertions depend on default values: test_serving asserts the literal dataset names ('p.serving.serving_pevs_annual', 'p.gold.gold_source_metadata'), `recorded["params"]["reporter"].value == "BRA"` (comtrade_brazil_iso), and `Settings(gcp_project_id="p").cache_default_timeout > DEFAULT_CLASSIFICATION_TTL` (CACHE_DEFAULT_TIMEOUT). A dev who sets BQ_SERVING_DATASET=dbt_dev_serving or CACHE_DEFAULT_TIMEOUT=15 in .env gets spurious local failures (or worse, spurious passes masking a regression). The project demonstrably knows the hazard — test_config.py, test_cli.py, test_ibge_pipeline.py, test_pam_pipeline.py, test_comtrade_pipeline.py, test_core_raw.py, test_bcb_series.py all pass `_env_file=None` — the isolation is just inconsistently applied, and there is no conftest.py to centralize it.

#### All GET read endpoints of the /api blueprint untested at the HTTP layer

- **Where**: `tests/test_webapi_routes.py`:1
- **Category**: test-gap · **Area**: tests-quality

test_webapi_routes.py covers only /healthz, the curation POST auth matrix (401/400/403), the JSON error handler via /api/catalog, and change_id forwarding. None of the 14 GET read endpoints in routes.py (/snapshot, /source-meta, /product-uf, /productivity, /flow, /partners, /monthly, /cross/metric-refs, /cross/series, /cross/export-coef, /cross/market-share, /cross/price-spread, /cross/mirror, /cross/value-added, /cross/market-nature, /curation/worklist, /curation/flow-worklist) has any test — query-param parsing (currency/correction passthrough, y0/y1 type=int coercion, startDate/endDate→summary construction at routes.py:114-115, crop default) and the route→seam→serializer wiring are unpinned. The POST /curation/flow-market endpoint (the second writer, with its distinct market-may-be-empty validation at routes.py:254-259) also has zero route-level tests, while its sibling /curation/code-level has five.

#### Cross-source analytics silently fall through to ALL-commodities totals when a commodity has no codes for a source

- **Where**: `src/embrapa_commodities/webapi/seam.py`:446
- **Category**: bug · **Area**: webapi-seam

_codes() returns an empty tuple when the selected commodity has no codes for a source (e.g. its NCM prefix matched nothing in Gold) or when the commodity id is unknown, and an empty tuple means 'no filter' to every gateway reader. market_share(), export_coefficient(), price_spread() and trade_mirror() pass that straight through, so e.g. a mass commodity with no resolved COMEX codes gets its export coefficient computed from the exports of ALL Brazilian trade divided by that one commodity's production (coefficients far above 100%), and market_share's per-commodity by_product loop computes b = ALL exports / commodity world exports. The result is presented as if scoped to the commodity. market_nature() contains an explicit guard against exactly this fallthrough (with a comment naming the hazard), proving the behavior is recognized as wrong; the four other producers lack it. _is_mass_basis only validates the PEVS side, so it does not protect the COMEX side of export_coefficient/price_spread.

#### export_coefficient by-UF/national compares unaligned windows: PEVS production since 1986 vs COMEX exports since 1997

- **Where**: `src/embrapa_commodities/webapi/seam.py`:544
- **Category**: bug · **Area**: webapi-seam

The per-UF and national export coefficients divide cumulative COMEX export weight by cumulative PEVS production with no year bounds on either reader. PEVS coverage starts in 1986 while COMEX starts in 1997 (and their end years can also differ), so the denominator includes ~11 years of production that can have no matching export data — systematically understating coefPct. The timeseries in the same payload correctly intersects the two sources' years (sorted(set(pevs_mass) & set(exp_mass))), so the static ranking and the timeseries in one response are computed over different windows and will disagree with each other.

#### COMEX Sankey mixes import rows into 'UF de origem -> pais parceiro' links (no flow filter)

- **Where**: `src/embrapa_commodities/webapi/seam.py`:261
- **Category**: bug · **Area**: webapi-seam

flow_data() builds the directed Sankey labeled 'UF de origem -> país parceiro' from fetch_comex_flows without passing flow='export', so import rows are summed into the same directed links. In MDIC COMEX, SG_UF_NCM is the UF *of the product*: origin UF for exports but destination UF for imports, and the partner country is the goods' origin on imports — i.e., for import rows the real direction is country->UF, yet their value is added to the UF->country link. The gateway/SQL builders expose a flow parameter (used correctly by export_coefficient with flow='export'), so the omission here inflates and mislabels every link in the territorial-flows view. The same unfiltered exp+imp sum feeds snapshot uf_data and product_uf_ranking for COMEX (seam.py:122-126, 199), where 'Onde X é produzido' becomes total trade rather than origin value.

#### Crosswalk/catalog cached for process lifetime via lru_cache — nightly dbt rebuilds never reach a warm Cloud Run instance

- **Where**: `src/embrapa_commodities/webapi/seam.py`:420
- **Category**: bug · **Area**: webapi-seam

_crosswalk_df, commodity_catalog, _pevs_family_by_commodity and _code_to_commodity are functools.lru_cache(maxsize=1) — cached forever per process. The crosswalk and gold_pevs_production families they read are rebuilt by the daily dbt run, so a long-lived Cloud Run instance keeps serving a stale /api/catalog, stale curation-worklist commodity grouping, and stale mass-basis gating until the instance happens to recycle. This contradicts the serving layer's own caching policy (every gateway read uses flask-caching TTLs sized to 'every instance independently converges to the same data within the TTL', gateway.py:9-20). New commodities/codes added by a dbt build are invisible to the API indefinitely.

#### value_added issues 2 BigQuery queries per classified code per request (N+1)

- **Where**: `src/embrapa_commodities/webapi/seam.py`:752
- **Category**: performance · **Area**: webapi-seam

value_added() loops over every code currently classified bruta/processada and calls _xyear twice per code (exp_value + exp_weight), each a separate parameterized BigQuery query via fetch_cross_series((code,)). With N classified NCM codes, a cold /api/cross/value-added request runs 2N sequential BQ round-trips (seconds each on a cold cache), scaling linearly as curators classify more codes — easily exceeding request timeouts. fetch_cross_series already accepts a tuple of codes, so the level split could be served with 2 queries per level (4 total) by passing the full code set per level, or one grouped query.

#### Trade-mirror payload omits the contracted `partners` series field — ViewMirror's third line ('Reportado pelos parceiros') is always empty

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:407
- **Category**: doc-mismatch · **Area**: webapi-serializers

The TradeMirror contract defines series rows as {y, mdic, comtrade, partners} (contracts.js:132). seam.trade_mirror builds rows with only {y, mdic, comtrade} and serialize_trade_mirror passes them through unchanged. The live 'Espelho comercial' view renders three lines, the third reading d.partners — undefined for every point — so the chart silently shows a legend entry ('Reportado pelos parceiros') with no data, and the KPI prose ('Parceiros tendem a registrar mais') refers to a series that never arrives. Either the partner-reported series should be produced (COMTRADE where partner=Brazil) or the contract/view should drop the third source; today the mismatch ships a permanently dead chart line.

#### _uf_data hardcodes q_mass/q_vol = 0.0 — ViewGeography's 'Quantidade (massa/volume)' toggles render all-zero maps presented as real data

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:247
- **Category**: data-quality · **Area**: webapi-serializers

The snapshot's ufData rows always carry q_mass: 0.0 and q_vol: 0.0 (the per-UF reader only returns total_value). But ViewGeography offers 'Quantidade (massa)' and 'Quantidade (volume)' dimension toggles whenever the banco's products include those families (true for PEVS/PAM/COMEX), and reads ufData.q_mass/q_vol for the choropleth/tile map and rankings. Users selecting those dimensions get an all-zero map ('—' in every cell) indistinguishable from real zero production — there is no in-product placeholder, only a code comment acknowledging the gap. This breaks the project's own 'honest placeholder' rule for unservable data: the capability is offered in the UI but silently returns fabricated zeros.

#### COMTRADE coverage drift: backend registry says 2022–2023, frontend registry says 1988–2024 — comparable-window math and user-facing coverage claims disagree

- **Where**: `src/embrapa_commodities/webapi/registries.py`:193
- **Category**: inconsistency · **Area**: webapi-serializers

registries.py declares COMTRADE metric coverage [2022, 2023] with maturity_note 'Cobertura inicial 2022–2023' (matching the intentional ingestion cap), but the frontend's bancos.js — which is what the UI actually reads — declares years [1988, 2024], cobertura '1988 → presente', and a different maturity note ('Backfill histórico (1988–2010) parcial'). The client's crossCommonWindow computes the comparable window from ITS registry (so PEVS×COMTRADE intersects to 1988–2024 instead of 2022–2023), while the server's SeriesResult.coverage returns [2022,2023]; the two layers ship contradictory coverage to the same view, and the frontend's user-facing claim overstates what Gold holds. The frontend PAM entry also carries maturityDate '1º trimestre/2027' that the Python Banco lacks.

#### registries.py view/filter/maturity registries are dead code that has already drifted (productivity 'soon' vs live), under a 'single source of truth' docstring

- **Where**: `src/embrapa_commodities/webapi/registries.py`:467
- **Category**: dead-code · **Area**: webapi-serializers

Only Banco and banco_by_id are imported anywhere (seam.py:29). MATURITY, CAPABILITIES, View/ViewGroup/VIEW_GROUPS/VIEW_BY_ID, view_by_id/view_label/is_view_live/view_applies_to/bancos_supporting/missing_caps_label, VALUE_PRESETS, TIER_LABEL, FILTER_SCHEMAS/filter_schema_for, maturity_meta, banco_availability, visible_bancos and canon_currency_for have zero callers in src/ or tests/ — the UI derives these from frontend/src/proto/{views,bancos,filtersSchema}.js. The dead copy has already drifted: the Python View('productivity', ..., 'soon') (not exportable) contradicts the shipped feature (frontend views.js status 'live', exportable: true; /api/productivity wired end-to-end per commit 25821f4), and FILTER_SCHEMAS is internally inconsistent (PEVS dims carry 'num': '01'… keys; the COMEX/COMTRADE dims have none). The module docstring 'Registries — the single source of truth for bancos, perspectives, and filters' is therefore misleading: any future reader would update the wrong place.


### Severity: low

#### doctor COMEX probe hard-fails on the expected current-year 404 the pipeline itself treats as healthy

- **Where**: `src/embrapa_commodities/doctor.py`:186
- **Category**: bug · **Area**: app-infra-python

_check_comex HEADs EXP_<COMEX_END_YEAR>.csv, and comex_end_year defaults to the CURRENT year (config.py:148). Early in each year, MDIC has not yet published that file, so the HEAD 404s and the check returns ok=False — which makes `embrapa doctor` exit 1 (cli.py:793-795). The comex ingest pipeline explicitly classifies that same condition as an expected skip ('a legitimate current-year 404'), so doctor reports the environment as broken while every ingest would succeed. Any cron/CI gate on doctor goes red for weeks every January.

#### doctor serving-marts check permanently flags the gold_source_metadata view as 'empty' (num_rows is 0, not None, for views)

- **Where**: `src/embrapa_commodities/doctor.py`:305
- **Category**: bug · **Area**: app-infra-python

_check_serving_marts assumes `tbl.num_rows` is None for views ('0 only for an empty materialized mart; None for views', and the docstring claims existence-only for gold_source_metadata). Verified against the live BigQuery API: tables.get for the gold_source_metadata VIEW returns numRows:"0", so google-cloud-bigquery's Table.num_rows is the int 0 and the view lands in the '⚠ empty=[...]' list on every doctor run even when everything is healthy — a permanent false alarm that trains operators to ignore the empty-mart warning, masking real empty marts.

#### monitor --pipeline filter prefix-collides: 'ibge' matches ibge-batch and ibge-pam logs

- **Where**: `src/embrapa_commodities/observability.py`:87
- **Category**: bug · **Area**: app-infra-python

latest_log_path filters with glob f"{pipeline}-*.jsonl" while log filenames are f"{pipeline}-{run_id}.jsonl" and pipeline names themselves contain hyphens (ibge-batch, ibge-pam, bcb-inflation, bcb-currency). `embrapa monitor --pipeline ibge` therefore attaches to the most recent of ibge-, ibge-batch- OR ibge-pam- logs — the CLI help explicitly offers 'ibge' and 'ibge-batch' as distinct filters, so the user watching an `ingest ibge` run can silently be shown a PAM/batch run instead. test_observability only covers non-overlapping prefixes (ibge vs bcb), so the collision is untested.

#### RotatingFileHandler rotation breaks the monitor's append-only tail protocol (silent event loss/freeze)

- **Where**: `src/embrapa_commodities/observability.py`:60
- **Category**: bug · **Area**: app-infra-python

The module docstring guarantees 'Events are append-only and ordered. The monitor relies on ordering', yet init_run installs a RotatingFileHandler (maxBytes=10MB, backupCount=5). On rollover the live file is renamed to *.jsonl.1 and a fresh empty file replaces it; the monitor's _tail_jsonl reopens the path each tick and seeks to last_position — now past EOF — so it reads nothing and keeps the stale offset, silently freezing until the new file grows past the old byte offset (up to 10MB of events skipped, then resumes mid-stream). Rotated *.jsonl.N files also stop matching the *.jsonl glob in latest_log_path/list_log_paths. Reachable on large COMTRADE backfills (252 reporters × retry/truncated events).

#### doctor's '.env parsed' check does not exercise the PAM/COMEX/COMTRADE parsers it implicitly vouches for

- **Where**: `src/embrapa_commodities/doctor.py`:40
- **Category**: test-gap · **Area**: app-infra-python

_check_env only evaluates inflation_series_map, currency_series_map and product_codes. The lazily-parsed properties comex_ncm_map, comex_chapter_map, comex_flows_list, comtrade_cmd_map, comtrade_flows_list and pam_product_codes_list (all of which raise ValueError on malformed input, config.py:276-339) are never touched, so a malformed COMEX_NCM_CODES or COMTRADE_FLOWS passes '.env parsed ✓' and only explodes mid-ingest — exactly the failure mode doctor exists to pre-empt ('validate .env parsing ... before kicking off a long ingest', doctor.py:3-6).

#### Monitor shows a bogus 'Chunk states 0/27' bar and rows=0 for non-IBGE pipelines

- **Where**: `src/embrapa_commodities/monitor/render.py`:167
- **Category**: inconsistency · **Area**: app-infra-python

_build_progress adds the per-chunk states row with total=STATES_PER_CHUNK (27 Brazilian UFs) whenever ANY chunk is active, but only the IBGE SIDRA client emits state_start/state_end events — COMEX/COMTRADE/BCB never do, so their monitor view shows a frozen 'Chunk states 0/27' bar with ETA '?'. Related contract gaps: _on_chunk_end reads ev.get('rows') but ChunkTracker.finish never includes a rows field (only ibge/pam emit ingest_loaded), so COMEX/COMTRADE runs always display 'rows 0'; and _summarize_retry reads ev['state'] while comex/comtrade retries emit 'series', rendering 'retry ? attempt=...'. The monitor is explicitly advertised for COMEX ('Emits a chunk per (flow, year) for live `embrapa monitor` progress', cli.py:429).

#### Stale 'stateless Dash app' references in config.py and .env.example (Dash UI was removed)

- **Where**: `src/embrapa_commodities/config.py`:193
- **Category**: doc-mismatch · **Area**: app-infra-python

The serving-dataset comments in both config.py and .env.example still describe the consumer as 'the stateless Dash app', but the Dash UI was entirely replaced by the React SPA + Flask webapi in the 2026-06 migration (the Dash package was deleted). A reader configuring BQ_SERVING_DATASET is pointed at a component that no longer exists.

#### .env.example omits BQ_FLOW_MARKET_LOG_TABLE while documenting its two sibling curation log tables

- **Where**: `.env.example`:206
- **Category**: doc-mismatch · **Area**: app-infra-python

config.py defines three curation log tables (commodity_processing_stage_log, code_industrialization_log, flow_market_log) and the serving layer reads/writes all three (serving/curation.py:413-460, serving/gateway.py:428), but .env.example documents only the first two. An operator renaming the curation tables for a portable deployment ('Every name below ... is configurable', .env.example:3) would miss the flow-market log entirely.

#### .env.example PAM comment promises a floating end year but the example value pins it to 2024

- **Where**: `.env.example`:90
- **Category**: inconsistency · **Area**: app-infra-python

The PAM block comment says 'The end floats with the current year so a routine run absorbs revisions + picks up a new year' — that describes the config.py default (default_factory=_current_year), but the very next line sets PAM_END_YEAR=2024, which overrides the default and stops the float for anyone who copies .env.example (today is 2026: PAM would be silently frozen at 2024 and never pick up 2025+). Unlike the IBGE block, which honestly instructs 'bump it manually after each IBGE release', the PAM comment claims behavior the pinned value disables.

#### doctor_cmd help text understates what doctor checks and which checks can fail

- **Where**: `src/embrapa_commodities/cli.py`:774
- **Category**: doc-mismatch · **Area**: app-infra-python

The `embrapa doctor` docstring (shown as CLI help) says it validates '.env parsing, ADC credentials, BigQuery / GCS reachability, IBGE SIDRA + BCB SGS connectivity, and whether Bronze tables exist yet' and that only the 'Bronze-tables check is informational'. In reality doctor also probes PAM, COMEX, COMTRADE, serving marts and Gold-backup freshness — and the backup-freshness check returns ok=False (exit 1) when no snapshot exists, which the help never mentions. A fresh-project user sees doctor fail for a reason the help says isn't checked.

#### deploy.sh smoke-check instruction points at /api/healthz, but healthz is registered at /healthz — the given URL returns the SPA index.html

- **Where**: `deploy/webapi/deploy.sh`:125
- **Category**: doc-mismatch · **Area**: cross-cutting-infra

The post-deploy verification text tells the operator that '/api/healthz returns {"status":"ok"}'. The health endpoint is registered app-level at /healthz (outside the /api blueprint). In the deployed image the SPA catch-all route (`/<path:path>`) matches 'api/healthz' and serves index.html with HTTP 200 — so the documented check 'passes' while testing nothing, and any uptime check configured from this instruction would silently monitor the SPA shell instead of the API.

#### Env vars consumed by code/deploy scripts but absent from .env.example: COMTRADE_BRAZIL_ISO, BQ_FLOW_MARKET_LOG_TABLE, WEBAPI_*, INGEST_SCHEDULE_SA

- **Where**: `.env.example`:196
- **Category**: doc-mismatch · **Area**: cross-cutting-infra

.env.example claims to document every configurable name ('Every name below ... is configurable'), and even has a dedicated deploy-time section for the ingestion Job (INGEST_JOB_*, RECONCILE_*, COMTRADE_SCHEDULE_*), but several consumed variables are missing: COMTRADE_BRAZIL_ISO (config.py:174, forwarded by the webapi deploy allowlist — drives the Brazil-vs-world split in serving), BQ_FLOW_MARKET_LOG_TABLE (config.py:208, backs the flow-market curation log actively used by curation.py/gateway.py — its two sibling log tables ARE documented), the whole WEBAPI_* deploy-time family (deploy/webapi/deploy.sh reads WEBAPI_REGION from .env exactly like INGEST_JOB_REGION, plus WEBAPI_SERVICE_NAME/SA/MEMORY/etc. as env overrides — no .env.example section exists for the webapi Service), and INGEST_SCHEDULE_SA (read by all three schedule scripts). Operators cannot discover these knobs from the template; renaming the flow-market table or pointing the webapi at another region requires reading source.

#### Makefile .PHONY still declares removed dashboard-run/dashboard-deploy targets; webapi-run/webapi-deploy missing from .PHONY

- **Where**: `Makefile`:4
- **Category**: dead-code · **Area**: cross-cutting-infra

The .PHONY list was not updated at the Dash→React cutover: it declares `dashboard-run dashboard-deploy`, which no longer exist as targets anywhere in the file, while the replacement targets `webapi-run` (line 65) and `webapi-deploy` (line 68) are not declared phony. Today this is stale-reference noise plus a latent hazard: a file or directory named `webapi-run`/`webapi-deploy` in the repo root would make make report 'up to date' and skip the recipe.

#### schedule_comtrade.sh claims the monthly Comtrade run 'never overlaps' the nightly, but its 6h default timeout starts 1h before it

- **Where**: `deploy/ingestion/schedule_comtrade.sh`:61
- **Category**: inconsistency · **Area**: cross-cutting-infra

The script's comment asserts the 15th-of-month 04:00 BRT trigger is placed 'away from the 1st-of-month reconcile (03:00) and the nightly (05:00), so the heavy quota-limited run never overlaps them' — yet the same script sets a default per-execution timeout of 21600s (6h), so the Comtrade execution may legitimately run until ~10:00 BRT, concurrent with the 05:00 BRT nightly `ingest all` and the 11:30 UTC (08:30 BRT) scheduled prod dbt build. The Bronze tables differ so no write contention occurs, but an operator relying on the stated serialization (e.g. when reasoning about quota, egress, or a mid-build partial Comtrade year reaching Silver/Gold a day early) is misled.

#### ci.yml calls the repo 'a private team repo' while gitleaks.yml calls it 'a public/personal repo' — one fork-handling rationale is wrong

- **Where**: `.github/workflows/ci.yml`:160
- **Category**: inconsistency · **Area**: cross-cutting-infra

Two workflows justify their security posture with contradictory claims about the same repository. ci.yml's sqlfluff job skips fork PRs arguing 'this is a private team repo so forks don't arise in practice'; gitleaks.yml omits GITLEAKS_LICENSE arguing 'this is a public/personal repo'. Both cannot be true. If the repo is public, fork PRs are realistic and the sqlfluff job (a recommended required check) silently passes as 'skipped' for them — exactly the scenario the ci.yml comment dismisses; if it is private/org-owned, gitleaks-action v2 requires a license key and the gitleaks gate would start failing.

#### .dockerignore does not exclude frontend/node_modules or frontend/dist — the documented local docker build merges host artifacts into the SPA build stage

- **Where**: `.dockerignore`:27
- **Category**: bug · **Area**: cross-cutting-infra

The webapi Dockerfile documents a local build path (`docker build -f deploy/webapi/Dockerfile -t embrapa-webapi .`) whose context is the repo root, and stage 1 runs `npm ci` then `COPY frontend/ ./`. .dockerignore (self-described as 'Build context hygiene for any image built from this repo') excludes Python caches and .env but not frontend/node_modules or frontend/dist — both are only in .gitignore. On a machine where `npm install`/`npm run dev` has been run, a local docker build ships hundreds of MB of context and the COPY overlays the clean Linux `npm ci` install with host (e.g. darwin-arm64) node_modules, which can break or subtly poison `npm run build` with platform-mismatched binaries. The Cloud Build path is only safe by accident (gcloud synthesizes .gcloudignore from .gitignore).

#### Serving YAML claims full {nominal, IPCA, IGP-M, IGP-DI} × {BRL, USD, EUR} matrix but marts omit IGP-M/IGP-DI × USD

- **Where**: `dbt/models/serving/_serving.yml`:10
- **Category**: doc-mismatch · **Area**: dbt-serving-core

The descriptions of serving_pevs_annual (_serving.yml:10-12) and serving_pam_annual (_serving.yml:42-44) state monetary measures 'span {nominal, real IPCA/IGP-M/IGP-DI} × {BRL, USD, EUR}', but both marts carry only 10 of those 12 columns: val_real_igpm_usd and val_real_igpdi_usd are not selected (serving_pevs_annual.sql:49-55, serving_pam_annual.sql:49-55) even though Gold computes them (gold_pevs_production.sql:233,238). A researcher selecting USD + IGP-M in the dashboard is silently downgraded to BRL by the seam fallback (seam.py:50-57), and anyone reading the YAML (persist_docs pushes these descriptions into BigQuery for Looker users) will look for columns that don't exist.

#### n_cities counts DISTINCT city_name despite Gold's explicit warning that city_name is not a key

- **Where**: `dbt/models/serving/serving_pevs_annual.sql`:56
- **Category**: inconsistency · **Area**: dbt-serving-core

gold_pevs_production groups by city_code precisely because 'two municipalities can share a name' and calls city_name a display label lifted via any_value(). Yet serving_pevs_annual.sql:56 and serving_pam_annual.sql:56 compute n_cities as count(distinct city_name) instead of count(distinct city_code). If two municipalities inside the same UF ever carry the same name (or a name normalization collision occurs), n_cities silently undercounts; using city_code is strictly safer and is the project's own documented convention.

#### serving_comtrade_annual comment claims a mixed-unit HS6 split that can never occur

- **Where**: `dbt/models/serving/serving_comtrade_annual.sql`:38
- **Category**: inconsistency · **Area**: dbt-serving-core

The model comment (copy-pasted from serving_comex_annual) says putting family in the GROUP BY 'correctly splits the rare mixed-unit HS6'. It cannot: silver_comtrade_flows deduplicates to exactly ONE row per (refYear, reporter, partner, cmd, flow) — qtyUnitCode is deliberately NOT in the dedup partition — and gold_comtrade_flows is tested unique on that same 5-column key, so every Gold row already carries a single family and adding family to the serving GROUP BY is a no-op. The comment gives false assurance that mixed-unit reporting is preserved/split at serving when in fact the non-dominant unit variant was discarded upstream in Silver. It also quietly contradicts the YAML test (which, unlike COMEX's, correctly omits family from the tested key because the split is impossible).

#### dim_code_industrialization_scd2: 'at most one is_current per (source, code)' is asserted in docs but never tested

- **Where**: `dbt/models/core/_core.yml`:100
- **Category**: test-gap · **Area**: dbt-serving-core

The companion view dim_commodity_scd2 enforces its SCD2 invariant with a `unique` test on commodity_id filtered to is_current rows (_core.yml:76-78). dim_code_industrialization_scd2's description claims the same guarantee ('The SCD2 window guarantees at most one is_current row per (source, code)') but defines no equivalent test — there is no dbt_utils.unique_combination_of_columns on (source, code) with where is_current. If the view logic or the log writer ever regresses (e.g. duplicate change_id rows slipping past the writer's idempotency check), duplicate 'current' classifications would flow undetected into the value-added split (seam.value_added builds a dict keyed on (source, code), silently keeping an arbitrary winner).

#### Stale references to the removed Dash app in serving-layer comments

- **Where**: `dbt/models/serving/serving_pevs_annual.sql`:19
- **Category**: doc-mismatch · **Area**: dbt-serving-core

The Dash UI was removed entirely in the 2026-06 Dash→React migration (per CLAUDE.md the package no longer exists), but the serving layer's rationale comments still name it as the consumer: serving_pevs_annual.sql:19 ('lets the stateless Dash app push a parameterized GROUP BY down to BigQuery') and dbt_project.yml:41 ('pre-aggregated marts for the Dash app's Pushdown Computing'). Same drift in _gold.yml:13 ('For the Dash dashboard's Pushdown Computing'). Misleads anyone tracing the serving layer's consumers; the actual consumer is the Flask webapi BFF + React SPA.

#### Comtrade dedup ranks unit-preference ABOVE ingestion recency, so a stale row can shadow a corrected re-publication

- **Where**: `dbt/models/silver/silver_comtrade_flows.sql`:68
- **Category**: bug · **Area**: dbt-silver-gold

The #102 de-double-count fix collapses qtyUnitCode variants with `order by (qtyUnitCode = '-1'), ingestion_timestamp desc` — the unit preference is the PRIMARY sort key, recency only the tiebreaker. If UN Comtrade re-publishes a (reporter, partner, cmd, flow, year) record with a corrected primaryValue but only under the '-1' (no-quantity) variant — or stops publishing the measured-unit variant — the OLD measured-unit row from an earlier ingestion permanently outranks the newer corrected row, freezing the stale value. This inverts the project-wide 'dedupe by ingestion_timestamp desc' contract. Safer: dedup by recency first, or apply the unit preference only among rows of the same (latest) ingestion batch. Also, the comment at lines 65-66 cites "'12' kg" as an example, but per seeds/comtrade_unit.csv code 12 is m³ and kg is code 8 — a misleading example in a load-bearing comment.

#### gold_comex_flows sums qty_native/qty_base across statistical units it deliberately excludes from the GROUP BY

- **Where**: `dbt/models/gold/gold_comex_flows.sql`:56
- **Category**: data-quality · **Area**: dbt-silver-gold

base_flows groups by (flow, year, month, ncm, country, uf, via) but NOT stat_unit_code, then `sum(qty_native)` and `sum(qty_base)` over the group. The array_agg trick makes the unit LABELS coherent (picked from the dominant-quantity row), but the SUMS still add quantities reported under different statistical units — and qty_base can even add across different families (m³ + t), which the project's own rule forbids ('NEVER sum qty_base across families'). This bites whenever an NCM's statistical unit changes within a cell (e.g. an MDIC unit reclassification creating a transition month, or restated files mixing vintages): the total is labeled with one unit but contains another. Either include stat_unit_code in the grain (as Silver does) or sum qty only over rows matching the dominant unit.

#### assert_family_base_unit_coherent omits gold_pam_production

- **Where**: `dbt/tests/assert_family_base_unit_coherent.sql`:22
- **Category**: test-gap · **Area**: dbt-silver-gold

The coherence guard pinning the family↔base_unit pairing invariant ('a future edit can't reintroduce the mismatch') unions gold_pevs_production, gold_comex_flows and gold_comtrade_flows — but gold_pam_production, added later with the identical family/base_unit columns and the same max()-lift pattern (gold_pam_production.sql:43-47), is not included. A regression in PAM's unit-family wiring (e.g. independent max() pairing family from one row with base_unit from another) would pass the test suite.

#### gold_comex_flows grain documentation contradicts itself: header and YAML say transport route is summed away, but it is part of the grain

- **Where**: `dbt/models/gold/gold_comex_flows.sql`:15
- **Category**: doc-mismatch · **Area**: dbt-silver-gold

The model header states the grain is '(flow, reference_year, reference_month, ncm_code, country_code, state_acronym)' and that 'the Silver source grain (which also splits by transport route / customs office / statistical unit) is summed up to this grain here'. The actual GROUP BY (line 65-67) and the dbt_utils.unique_combination_of_columns test (_gold.yml:176-185) both include transport_route_code, and the column's own description says 'Part of the grain; backs the frontend via filter' (_gold.yml:227). The yml model description (lines 165-168) repeats the wrong 6-column grain. A Looker user or developer trusting the table description would assume one row per (flow,month,ncm,country,uf) and double-count across transport routes when picking rows instead of aggregating.

#### Stale 'Dash' dashboard references in dbt comments/descriptions after the React migration removed Dash

- **Where**: `dbt/dbt_project.yml`:41
- **Category**: doc-mismatch · **Area**: dbt-silver-gold

The 2026-06 migration replaced the Dash UI entirely (per CLAUDE.md: 'the Dash package was removed after the cutover — don't look for dashboard/'), but dbt still documents the serving layer as built 'for the Dash app's Pushdown Computing' (dbt_project.yml:41) and gold_pevs_production's persisted description says 'For the Dash dashboard's Pushdown Computing' (_gold.yml:13-14). Because +persist_docs is on, the wrong description is also pushed into the BigQuery table metadata that Looker/console users read.

#### User-facing COMTRADE labels are English while the parallel COMEX labels are Portuguese (project language rule)

- **Where**: `dbt/seeds/_seeds.yml`:196
- **Category**: inconsistency · **Area**: dbt-silver-gold

comtrade_country ships 'English name' (e.g. 'Other Asia, nes') and comtrade_hs 'English HS description'; these flow into gold_comtrade_flows.partner_name/reporter_name/cmd_description, through serving_comtrade_annual, and out to the SPA verbatim (webapi/serializers.py:466 maps r.partner_name to the displayed "name"). The project rule says any string the end user could read must be Portuguese (default to Portuguese when unsure), and the sibling COMEX dimensions do exactly that (comex_country 'Portuguese name', comex_ncm 'Portuguese description', comex_via Portuguese labels). End users therefore see Portuguese country/product names in the COMEX view but English ones in the COMTRADE view of the same dashboard. Either translate the seed (it is regenerated by scripts/refresh_comtrade_country_seed.py, so a pt-BR name column could be joined/maintained) or document the verbatim-source-data exception explicitly.

#### Stale 'valores ilustrativos' captions on charts that now render real API data

- **Where**: `frontend/src/proto/ViewFlows.jsx`:30
- **Category**: inconsistency · **Area**: frontend-data-charts

Four chart headers still carry the synthetic-era caption 'valores ilustrativos' (illustrative values) even though the underlying producers were swapped to real endpoints (/api/flow, /api/monthly, /api/cross/export-coef, /api/cross/mirror) in the React migration. For a scientific dashboard this label tells researchers the live COMEX Sankey, seasonality heatmap, export-coefficient series and trade-mirror chart are demo data — the inverse of the project's honesty rule (PreviewBanner is reserved for genuinely synthetic data via the preview flag, which these payloads set to false).

#### contracts.js typedefs promise fields the API never emits (ProductivityData national/byUF extras; ValueAddedAnalysis priceB/priceP)

- **Where**: `frontend/src/proto/contracts.js`:90
- **Category**: doc-mismatch · **Area**: frontend-data-charts

contracts.js bills itself as 'THE SINGLE SOURCE OF TRUTH FOR DATA SHAPE', but the live serializers have drifted: ProductivityData promises national:{yieldKgHa,areaHa,prodT,yieldCagr} and byUF rows with areaHa/prodT — serialize_productivity emits national:{yieldCagr} only and byUF rows with only uf/name/region/yieldKgHa. ValueAddedAnalysis promises series rows with priceB/priceP — seam.value_added emits only y/brutaV/procV/procShare/premium. Today's views happen not to read the missing fields, and the runtime lint (auditSnapshotContracts) checks only top-level keys, so the drift is invisible — but any backend/frontend agent coding against the typedefs will produce silently-undefined reads.

#### FilterPreview shows the wrong Gold table for 'soon' bancos (banco object passed where id expected)

- **Where**: `frontend/src/proto/FilterMenu.jsx`:1089
- **Category**: bug · **Area**: frontend-proto-ui

FilterPreview receives the banco registry OBJECT (`banco={bancoMeta}`) but calls window.bancoTable(banco), which expects an id string. bancoById(object) finds nothing and falls back to BANCOS[0] (ibge_pevs), so the preview modal for any not-yet-live banco (e.g. SEFAZ NFe, reachable via the sidebar → 'Ver dimensões previstas') tells the user the dimensions will be available 'assim que a tabela gold_pevs_production for publicada' instead of gold_nfe_flows — in both the banner and the footer.

#### Stale `plannedRelease` field references — renamed to maturityDate, so 'previsão' never renders

- **Where**: `frontend/src/proto/FilterMenu.jsx`:688
- **Category**: dead-code · **Area**: frontend-proto-ui

No banco in the registry defines `plannedRelease` anymore (the maturity refactor renamed it to `maturityDate`, and dataStore.meta even keeps a `b.maturityDate || b.plannedRelease` compatibility fallback), but three UI spots still read banco.plannedRelease directly: the FilterMenu header for non-live bancos always falls back to 'em breve', FilterPreview's '(previsão …)' suffix never shows, and FilterTriggerBar's preview note never shows the date. Any future dated banco will silently lose its ETA in these surfaces.

#### Dev-only console messages written in Portuguese, violating the project language rule

- **Where**: `frontend/src/proto/views.js`:180
- **Category**: inconsistency · **Area**: frontend-proto-ui

The project rule says text read exclusively by developers (logs, operator messages) must be English; Portuguese is reserved for end-user-visible strings. Several console.warn diagnostics are in Portuguese: views.js's missing-component warning, bancos.js's coverage lint, contracts.js's shape-drift lint, and csvExport.js's export guards. These are developer diagnostics (never rendered in the UI), so per the stated rule they should be English.

#### COMEX _emit_retry misattributes head_source retries (emits 'ncm' as the series, logs the wrong URL)

- **Where**: `src/embrapa_commodities/comex/client.py`:118
- **Category**: bug · **Area**: ingestion-comex-comtrade

_emit_retry's docstring and arg-unpacking assume the retried function is _download_to_disk(url, dest): it takes args[0] as the URL and derives the monitor 'series' from its last path segment. But the same hook is also wired as before_sleep of head_source(base_url, flow, year) (client.py:185-190). For HEAD retries args[0] is the *base* URL, so the observability event is emitted with series='ncm' (the base path's last segment) for every (flow, year), and the warning log prints 'Retrying Comex download url=<base_url>' — a HEAD mislabeled as a download, with the actual flow/year (e.g. EXP_2023) unidentifiable. `embrapa monitor` users cannot tell which file's freshness probe is flapping, and all HEAD retries collapse into one bogus 'ncm' series. The docstring ('the retried function is _download_to_disk') is also stale relative to the second wiring.

#### doctor._check_comex probes the current-year file the pipeline itself expects to 404 (false 'COMEX unreachable' early each year)

- **Where**: `src/embrapa_commodities/doctor.py`:186
- **Category**: inconsistency · **Area**: ingestion-comex-comtrade

The doctor health check HEADs EXP_<comex_end_year>.csv and calls raise_for_status(), turning any 404 into CheckResult('COMEX reachable', False). comex_end_year defaults to the current calendar year (config.py:148), and the ingestion pipeline explicitly models a current-year 404 as 'an *expected* not-yet-published state, not a pipeline failure' (comex/pipeline.py:271-280, _is_current_year_missing). So in the weeks between Jan 1 and MDIC publishing the new year's file, `embrapa doctor` reports COMEX as unreachable/failing while the source and pipeline are perfectly healthy — the two layers contradict each other on the same condition. Probing the prior year (or treating a current-year 404 as a pass) would match the pipeline's contract.

#### Any keyed 429 is classified as daily-quota exhaustion and aborts the whole Comtrade run, with zero client-side throttling between calls

- **Where**: `src/embrapa_commodities/comtrade/client.py`:216
- **Category**: bug · **Area**: ingestion-comex-comtrade

fetch_chunk maps every HTTP 429 on a keyed data call to ComtradeQuotaError ('quota exhausted ... re-run to resume'), which pipeline.run() treats as a hard stop for the entire run (pipeline.py:420-424). But UN Comtrade's APIM enforces a per-second/burst rate limit *in addition to* the daily quota, both answering 429. The pipeline fires keyed calls back-to-back with no delay anywhere — the chunk loop (pipeline.py:405-419) and the adaptive splitter's recursive sub-calls (client.py:257-276) issue the next request immediately, and past-year chunks with little data return in milliseconds, so consecutive calls can easily land within the same second. A burst-induced transient 429 then aborts the run with the misleading 'quota exhausted' message instead of backing off for a few seconds (a Retry-After header, which would disambiguate the two cases, is never inspected). Impact is bounded because the run is resumable, but unattended scheduled runs (deploy/ingestion/schedule_comtrade.sh) terminate early and report quota exhaustion that never happened.

#### Bronze string coercion can land '0.0'/NULL breakdown codes that Silver's exact-match filters silently drop

- **Where**: `src/embrapa_commodities/comtrade/client.py`:227
- **Category**: data-quality · **Area**: ingestion-comex-comtrade

fetch_chunk builds the Bronze frame with pd.DataFrame(rows).reindex(columns=BRONZE_COLUMNS).astype('string'). Two coercion paths produce values Silver cannot match: (1) the code itself anticipates sparse responses — 'missing columns (a sparse response) are added as NA via reindex' — which land as SQL NULL for motCode/customsCode/mosCode/partner2Code; (2) if any row in a response carries a JSON null in an otherwise-integer column, pandas floatifies the whole column, so motCode 0 becomes the string '0.0' (and qtyUnitCode -1 becomes '-1.0'). silver_comtrade_flows.sql keeps only rows where motCode = '0' AND customsCode = 'C00' AND partner2Code = '0' AND mosCode = '0' (exact string equality; NULL never matches), so every row from such a response silently vanishes from Silver/Gold with no data_quality_flag, no log, and no test failure — the chunk is marked bronze_loaded and never revisited. The '-1.0' variant would also defeat the qtyUnitCode-fix preference `order by (qtyUnitCode = '-1')` (silver line 68), keeping the no-quantity row over the kg row. Normalizing integer-coded columns at ingestion (strip a trailing '.0', or fail loudly on NULL breakdown codes) would close the gap.

#### PER_STATE_DEADLINE_S is neither per-state nor a hard ceiling as its comments claim

- **Where**: `src/embrapa_commodities/ibge/client.py`:103
- **Category**: inconsistency · **Area**: ingestion-ibge-bcb

Two overstatements about the same constant. (1) It is documented as 'Hard ceiling per state — after this many seconds across all retries, give up', but the http_retry_policy decorator wraps _http_get, i.e. ONE HTTP block call; _fetch_block's recursive period-halving issues multiple _http_get calls per state, each with its own 180s retry budget, so one state can legitimately run far past 180s. (2) tenacity's stop_after_delay only prevents STARTING a new attempt — it never interrupts a running one — so even a single _http_get can run to ~180s + REQUEST_TOTAL_DEADLINE_S (75s) ≈ 255s, contradicting 'a slow-byte hang can't keep the worker alive past PER_STATE_DEADLINE_S even if it never exhausts attempts'. Behavior stays bounded, but operators sizing Cloud Run job timeouts from these comments will under-provision.

#### Operator guidance 'Lower IBGE_END_YEAR to the latest published year' silently disables the delta's revision absorption

- **Where**: `src/embrapa_commodities/ibge/pipeline.py`:96
- **Category**: doc-mismatch · **Area**: ingestion-ibge-bcb

The empty-fetch warning (and the matching CLI message) instructs the operator to pin IBGE_END_YEAR to the latest published year. But _delta_start_year returns None (clean no-op) whenever the latest Bronze year >= ibge_end_year — so once Bronze reaches that pinned year, every nightly delta run skips entirely and PEVS revisions of recent years are never re-fetched until the monthly reconcile. This contradicts the documented delta contract (CLAUDE.md/config: the delta 're-fetches from latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS forward — absorbing PEVS revisions of recent years'; config.py explains END must FLOAT with the current year precisely so the nightly delta absorbs revisions). Following the printed advice quietly trades away that guarantee. The same conflicting advice text exists in pam_pipeline.py (line ~107) and cli.py.

#### fetch_curators TTL not bound to CACHE_CLASSIFICATION_TIMEOUT, contradicting its docstring and the runbook

- **Where**: `src/embrapa_commodities/serving/cache.py`:85
- **Category**: inconsistency · **Area**: serving-layer

_bind_classification_ttl() rebinds the Settings-derived TTL onto fetch_current_classifications, fetch_current_code_industrialization, and fetch_current_flow_market, but NOT onto fetch_curators — which is decorated with the same hard-coded DEFAULT_CLASSIFICATION_TTL fallback (gateway.py:407) and whose docstring promises 'Short TTL (like the classification reads) so a Console add/remove takes effect within the window'. The runbook (docs/operations_runbook.md:37-38) likewise tells operators curator changes take effect within CACHE_CLASSIFICATION_TIMEOUT. In reality the allowlist read is pinned at 30s: an operator who lowers CACHE_CLASSIFICATION_TIMEOUT (e.g. to 5s for faster revocation of a removed curator — an authorization control) gets no effect on the curators cache; a revoked curator can keep writing for up to 30s regardless of the configured value.

#### Commodity-level curation path (record_processing_stage / fetch_current_classifications) is unreachable dead code since the React migration

- **Where**: `src/embrapa_commodities/serving/curation.py`:170
- **Category**: dead-code · **Area**: serving-layer

The entire commodity-level classification path — record_processing_stage (curation.py:170), invalidate_classification_cache (curation.py:257), ensure_curation_log_table (curation.py:111), CURATION_LOG_SCHEMA (curation.py:42), gateway.fetch_current_classifications (gateway.py:561), and sql.current_classifications (sql.py:261) — has no caller outside tests. The webapi exposes only the per-code (/curation/code-level) and flow-market (/curation/flow-market) writers (webapi/routes.py:223,246) and never reads dim_commodity_scd2; the React frontend has no processing-stage UI either. The module docstring still presents it as 'the backend of the dashboard's Save button', sql.py:263-265 still claims its result 'is the ONLY serving cache that a curation write invalidates', and the serving marts' comments still promise a live LEFT JOIN to dim_commodity_scd2 that no layer performs. Misleading maintenance surface: the cache short-TTL machinery and the dbt view are kept alive for a code path the product cannot trigger.

#### Serving package docstrings still describe the deleted Dash UI

- **Where**: `src/embrapa_commodities/serving/__init__.py`:1
- **Category**: doc-mismatch · **Area**: serving-layer

CLAUDE.md states the 2026-06 React migration 'replaced the Dash UI entirely (the Dash package was removed after the cutover)', yet the serving package's documentation still frames itself around Dash: __init__.py:1 'Data-access layer for the stateless Dash dashboard'; __init__.py:3-5 'It does NOT contain any Dash pages, layouts, or chart components — those arrive with the Claude Design System handoff' (the handoff already happened); cache.py:5-6 'passing its Flask server (Dash's underlying WSGI app)'; curation.py:183-184 'flask.request.headers in a Dash callback'; curation.py:260-261 'a CLI-driven write outside the Dash server'. A maintainer reading these will look for Dash callbacks/wiring that no longer exists; the real consumer is webapi (Flask app factory + React SPA).

#### Over-length curation input raises ValueError that the API surfaces as a 500 instead of a 400

- **Where**: `src/embrapa_commodities/serving/curation.py`:142
- **Category**: bug · **Area**: serving-layer

_validate_edit_text / _validate_code_edit / the market length check raise ValueError for user-supplied input that exceeds the caps (processing_stage/level/market > 200 chars, note > 2000 chars). The only caller-side guard in the webapi is a presence check (routes.py:234,258); the over-length case propagates to the blueprint-wide error handler (routes.py:31-39), which maps non-HTTPException to a generic 500 'internal server error'. So a POST to /api/curation/code-level or /api/curation/flow-market with a long level/market — which the serving layer deliberately validates as a client-input error — is reported as a server fault: wrong status code for monitoring (500s page operators), and the specific validation message is lost to the client. ValueError from the serving writers should be mapped to 400.

#### webapi/format.py has no tests; monetary_column↔ALLOWED_VALUE_COLUMNS contract unpinned

- **Where**: `src/embrapa_commodities/webapi/format.py`:135
- **Category**: test-gap · **Area**: tests-quality

There is no test file for webapi/format.py (no test_webapi_format.py; grep finds no test importing it). format.monetary_column() builds column names by string concatenation (f"val_{infix}_{suffix}") and seam.effective_value_column() validates the result against sql.ALLOWED_VALUE_COLUMNS, silently falling back to a BRL column when the name doesn't match. Nothing asserts that every (currency, correction) combo the UI offers maps into the allowlist — a one-character drift in _CORRECTION_INFIX/_CURRENCY_SUFFIX (or in ALLOWED_VALUE_COLUMNS) would make e.g. 'USD + IPCA' silently serve BRL data with a misleading label, and no test would fail. The pt-BR display formatters (fmt_brl, fmt_axis_tick, fmt_pct, _refresh_label callers) that end users read are also entirely untested.

#### test_init_cache_binds_classification_ttl_from_settings leaves persistent mutation on a shared module singleton

- **Where**: `tests/test_serving.py`:795
- **Category**: inconsistency · **Area**: tests-quality

The test calls init_cache(app, Settings(..., cache_classification_timeout=17)), which sets the writable `cache_timeout` attribute on the module-level decorated function gateway.fetch_current_classifications (flask-caching re-reads it per call). The mutation is never undone (no monkeypatch, no fixture teardown), so every test that runs after it in the same process executes with TTL 17 instead of the decoration-time DEFAULT_CLASSIFICATION_TTL=30. Today no later assertion reads the attribute, so the suite passes, but this is hidden cross-test order dependence on a shared singleton: a future test asserting the effective classification TTL (or relying on memoized entries surviving >17s in a slow CI run) would pass or fail depending on test ordering.

#### CLI `ingest ibge-pam` command has no dispatch test

- **Where**: `tests/test_cli.py`:51
- **Category**: test-gap · **Area**: tests-quality

test_cli.py pins argument parsing and dispatch for every other ingest subcommand (ibge, bcb-inflation, bcb-currency, comex, comtrade, ibge-batch, all, reconcile) including --full/--from-raw flag propagation, empty-return messaging, and error propagation, but the recently-added `ingest ibge-pam` command (cli.py:197-223, which wires pam_start_year/pam_end_year/pam_product_codes into the observability params and forwards full/from_raw) has zero CLI-level tests. The PAM pipeline itself is tested (test_pam_pipeline.py), but a regression in the command layer (e.g. dropping the from_raw forward, or pointing it at ibge_pipeline in a copy-paste) would not be caught — exactly the bug class the rest of test_cli.py exists to prevent.

#### exp_price cross series divides by 1 when a year's weight is missing, emitting raw US$ billions as 'US$/kg'

- **Where**: `src/embrapa_commodities/webapi/seam.py`:405
- **Category**: bug · **Area**: webapi-seam

_cross_points for mdic_comex:exp_price computes value/weight per year, but a year present in the value series and absent (or zero) in the weight series falls back to dividing by 1 ('or 1'), so the chart point becomes the year's total export value (potentially billions) plotted on a US$/kg axis — a catastrophic outlier rather than a skipped point. Years without weight should be omitted from the series (the way price_spread intersects fob/gate years). A related zero-instead-of-skip pattern exists in price_spread at seam.py:591 (gate=0 emitted as a real farm-gate price when PEVS quantity is missing, making spread=fob and markup=0 look like data).

#### Unknown /api/* paths return SPA index.html with HTTP 200 instead of a JSON 404

- **Where**: `src/embrapa_commodities/webapi/app.py`:88
- **Category**: bug · **Area**: webapi-seam

The SPA catch-all route ('/<path:path>') matches any /api path not explicitly registered on the blueprint, so a typo'd or removed endpoint returns index.html with status 200. The SPA's fetch layer checks r.ok (true) then r.json(), which fails with a parse error and burns its retry budget (frontend/src/data/resource.js MAX_ATTEMPTS) instead of receiving the machine-readable JSON error the /api error handler was built to guarantee ('Always emit parseable JSON from /api', routes.py:33-35). The catch-all should 404 (JSON) for paths under /api.

#### Dead code: seam.cross_common_window has no callers

- **Where**: `src/embrapa_commodities/webapi/seam.py`:340
- **Category**: dead-code · **Area**: webapi-seam

cross_common_window() is referenced nowhere in src/, routes, serializers, or tests (repo-wide grep finds only its definition); no /api endpoint exposes it and the frontend computes its own coverage intersection. Its dual key shapes (r.get('b') or r.get('banco')) and hard-coded fallbacks ((1997, 2024)) suggest a removed caller. Dead branches like the y0>y1 'union' fallback can silently rot if it is ever re-wired.

#### registries.py contradicts itself and the frontend: PAM described as 'no Gold / planejado placeholder' and productivity view still 'soon'

- **Where**: `src/embrapa_commodities/webapi/registries.py`:15
- **Category**: doc-mismatch · **Area**: webapi-seam

The module docstring and the BANCOS comment still state that IBGE PAM has no Gold table and is a 'planejado' placeholder, while the same file declares ibge_pam as maturity='beta' with table='gold_pam_production', and seam._LIVE_SOURCES serves it. Additionally, the 'productivity' View is status='soon' in the Python registry while the frontend's views.js (the registry it claims to faithfully port, 'single source of truth') marks it 'live' — drift introduced when #105 wired the PAM produtividade view end-to-end. Nothing in Python currently consumes View.status, but the file advertises itself as the source of truth for capability gating, so the drift will mislead the next consumer.

#### Configured classification TTL is not applied to the curator-allowlist read (auth freshness drift)

- **Where**: `src/embrapa_commodities/serving/cache.py`:85
- **Category**: inconsistency · **Area**: webapi-seam

_bind_classification_ttl() rebinds the Settings-derived cache_classification_timeout onto the three classification reads but not onto gateway.fetch_curators, which is also decorated with the static DEFAULT_CLASSIFICATION_TTL (30s) and whose docstring claims 'Short TTL (like the classification reads)'. The curator allowlist gates POST /api/curation/* authorization (routes._authorize_curator unions it into the allowlist), so changing CACHE_CLASSIFICATION_TIMEOUT in config affects classification reads but leaves allowlist staleness pinned at 30s — e.g. an operator who lowers the TTL to make a curator removal take effect faster gets no change on the authz path.

#### Trade snapshot value labeled 'Valor (US$ FOB)' for UN Comtrade, whose import values are CIF and which the overview sums in

- **Where**: `src/embrapa_commodities/webapi/seam.py`:48
- **Category**: data-quality · **Area**: webapi-seam

effective_value_column() returns the user-facing label 'Valor (US$ FOB)' for both trade bancos. For un_comtrade the snapshot overview sums exports and imports together (fetch_comtrade_overview is called without a flow filter), and UN Comtrade primary values for imports are reported on a CIF basis, so labeling the combined series 'US$ FOB' misstates the valuation basis shown to researchers in a scientific tool. The label is emitted verbatim as the snapshot's valueLabel.

#### serialize_productivity omits the contracted `preview` key and the national/byUF fields the ProductivityData typedef requires

- **Where**: `src/embrapa_commodities/webapi/serializers.py`:304
- **Category**: doc-mismatch · **Area**: webapi-serializers

SNAPSHOT_CONTRACTS.perBanco.productivity lists 'preview' among required keys, and the ProductivityData typedef defines national as {yieldKgHa, areaHa, prodT, yieldCagr} and byUF rows with areaHa/prodT. serialize_productivity's base dict has no 'preview' key (every other serializer stamps preview: False), national carries only yieldCagr, and byUF rows carry only uf/name/region/yieldKgHa. ViewProductivity happens to read only national.yieldCagr today, but the runtime contract lint (auditSnapshotContracts) will report 'falta `preview`' whenever it runs against a warm producer, and any view/export relying on the documented national/byUF fields gets undefined.

#### The formatter half of format.py is dead code (only 3 of ~15 exports are used), and the dead functions carry latent bugs

- **Where**: `src/embrapa_commodities/webapi/format.py`:27
- **Category**: dead-code · **Area**: webapi-serializers

Across src/ and tests/, only monetary_column, convention_value_label and MONTH_ABBR_PT are referenced (by seam.py/serializers.py). fmt_brl, fmt_money, fmt_num, fmt_pct, fmt_signed, fmt_rows, fmt_axis_tick, currency_symbol, symbol_for_column, convention_monetary_label, CURRENCY_LONG and DEFAULT_CONVENTIONS have zero callers — the React frontend does all user-facing formatting in JS (data.js). The dead code also harbors real defects that would bite anyone resurrecting it: fmt_axis_tick buckets by the ROUNDED-input magnitude so 999_950_000 renders '1.000 mi' instead of '1 bi' (and 999_999 → '1.000 mil'); _ptbr(float('nan')) returns the literal string 'nan' (only None is guarded); fmt_signed renders 0 as '+0,0%' while using U+2212 for negatives where fmt_brl/fmt_axis_tick use ASCII '-'. Verified by execution.


## Refuted (false positives — listed so they are not re-reported)

- **Idempotency dedupe echoes the caller's payload as written, even when it differs from the stored row** (`src/embrapa_commodities/serving/curation.py`): refuted with medium confidence.
- **mark_raw_bronze_loaded read-modify-write patches GCS metadata without a precondition (race re-opens the gap it exists to close)** (`src/embrapa_commodities/core/raw.py`): refuted with high confidence.
- **Inflation delta overlap formula floor-divides months, silently breaking for any non-multiple-of-12 setting** (`src/embrapa_commodities/bcb/inflation.py`): refuted with high confidence.
- **serving_comtrade_annual partition range (1970+) is narrower than its Gold source (1960+)** (`dbt/models/serving/serving_comtrade_annual.sql`): refuted with medium confidence.
- **Empty-window SIDRA test has no network guard — regression failure mode is 27 real HTTP calls** (`tests/test_ibge_client.py`): refuted with high confidence.
