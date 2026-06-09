# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Added
- **IBGE PEVS is now delta by default** (like the BCB). `ingest ibge` / `ingest all`
  re-fetch only from `latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS` (default 1)
  forward — absorbing PEVS revisions and a newly published year — instead of
  re-pulling 1986→today on every run (a huge request that blows SIDRA's slow-byte
  deadline on an unattended Cloud Run Job). `--full` forces the full window;
  `ingest ibge-batch` remains for the initial chunked historical backfill; a cold
  Bronze falls back to the full window. New helper `latest_reference_year`
  (`gcp/bigquery.py`) + `IBGE_DELTA_OVERLAP_YEARS` knob. Motivated by a Cloud Run
  Job smoke-run that failed on exactly this IBGE full-history fetch.
- **Architectural pivot — Pushdown Computing in the dashboard (replaces the
  in-memory/Pandas design, with its OOM/concurrency risk).** The Dash dashboard
  becomes **stateless**: UI filters turn into **parameterized SQL** (`@param`) on
  BigQuery, cached by **flask-caching**, instead of loading Gold tables into memory.
  - **dbt `serving/`**: marts pre-aggregated at the chart grains
    (`serving_pevs_annual`, `serving_comex_annual`, `serving_comex_seasonality`,
    `serving_comtrade_annual`, `serving_quality_by_source`) in the `serving` dataset
    (`BQ_SERVING_DATASET`), materialized as **tables** (cutting scan from GB→MB).
  - **dbt `core/`**: conformed dimensions `dim_date`, `dim_geo_br`; and the SCD
    Type 2 view `dim_commodity_scd2` (gated by `--vars 'enable_curation: true'`).
  - **Dynamic curation (SCD2)**: append-only log
    `research_inputs.commodity_processing_stage_log` (author captured from the IAP
    header `X-Goog-Authenticated-User-Email`); the UI does a live LEFT JOIN of the
    static mart to the classification dimension.
  - **Python BFF** (`src/embrapa_commodities/serving/`, optional `serving` extra):
    `sql` (@param + anti-injection allowlist), `gateway` (`@cache.memoize`), `cache`
    (flask-caching — `SimpleCache` scales multi-instance for free; `RedisCache`
    optional), `iap`, `curation` (append-only INSERT + cache invalidation).
  - **Multi-instance scaling without Redis (for free).** The dashboard scales to
    3–5+ Cloud Run instances without Memorystore: marts converge on
    `CACHE_DEFAULT_TIMEOUT` (overnight data) and the curation classification read
    uses a **short TTL** (`CACHE_CLASSIFICATION_TIMEOUT`, default 30s) that bounds
    the staleness between instances (eventual consistency ≤30s) — the instance that
    edits invalidates immediately. `RedisCache` becomes **optional** (only for
    instant cross-instance consistency under high traffic).
  - **Automated ingestion**: `embrapa ingest all` packaged as a **Cloud Run
    Job** (`deploy/ingestion/`: Dockerfile, cloudbuild.yaml, deploy.sh, schedule.sh)
    + **Cloud Scheduler** overnight (off-peak). Shortcuts `make ingest-job-deploy` /
    `make ingest-job-schedule`.
  - **Reverts the previous "never pre-aggregate" stance**: Gold remains the
    comprehensive per-source table (ad-hoc aggregation at query time), but `serving/`
    materializes pre-aggregated marts for Pushdown — they derive from Gold, they do
    not replace it.
- **New source: UN Comtrade (global bilateral trade) — `gold_comtrade_flows`.**
  A global complement to COMEX (Brazil): worldwide `reporter→partner` flows for
  HS **0801** (nuts) + **chapter 44** (wood/charcoal), ingested at the
  **HS6** level (scope expanded to the 156 six-digit leaves), across the **four
  primary regimes** X/M/RX/RM, all reporters × all partners, annual grain.
  - **Ingestion** (`embrapa ingest comtrade [--full] [--from-raw]`): a *keyed*
    JSON API (`COMTRADE_API_KEY`, free), with the key **only** in the
    `Ocp-Apim-Subscription-Key` header (never in the URL/log). Two-phase raw zone,
    *chunked* by `(year, batch of 8 reporters)` and **resumable**. **Adaptive
    split** against truncation (`fetch_chunk_adaptive`): when a call hits the
    100k-row cap (a single dense reporter already overflows it), it recursively
    splits reporters→flows→cmd and concatenates. It stays **outside
    `embrapa ingest all`** (key/quota-gated).
  - **dbt**: `silver_comtrade_flows` (keeps only the fully aggregated record —
    `motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0` — and HS6 only; drops
    the World partner `0`; normalizes `flowCode` X/M/RX/RM →
    `export`/`import`/`re-export`/`re-import`) and `gold_comtrade_flows` (the 4
    monetary conventions over `primaryValue` US$, **annual** deflation; bilateral
    reporter+partner geography via M49). Reuses `silver_currency` (USD/EUR/CNY) and
    `unit_family_conversions` (families).
  - **Seeds** of authoritative reference: `comtrade_country` (M49 → ISO3/name,
    `partnerAreas.json`), `comtrade_unit` (qtyUnitCode → family — 5=items, 8=kg,
    12=m³) and `comtrade_hs` (0801 + ch. 44, `HS.json`). Script
    `scripts/refresh_comtrade_country_seed.py`.
  - Initial historical window limited to **2022-2023** (config `COMTRADE_START_YEAR`/
    `COMTRADE_END_YEAR`) for development; extend later to older history.
- **Transport-modal dimension in COMEX (`via`).** `gold_comex_flows` gains
  `transport_route_code` (in the grain) + `via_name` via the new `comex_via` seed
  (MDIC CO_VIA codes → PT labels: Marítima, Aérea, Rodoviária…).
- **Cross-source product crosswalk** — seed `commodity_crosswalk` (links by
  *prefix*, at the commodity-concept level) + model `gold_commodity_crosswalk`
  (resolves to an exact `(source, code) → commodity`). Links the same commodity
  across PEVS (extractive code) / COMEX (NCM8) / COMTRADE (HS6) — the basis for the
  cross analyses (export coefficient, market share, trade mirror).
- **Data contract document** `docs/frontend_data_contract.md` — a Gold →
  frontend-snapshot map (field, magnitude, unit) for the BFF handoff.
- **Per-source provenance metadata** — view `gold_source_metadata` (one row per
  source: table, cadence, year coverage, counters `total_rows`/
  `products_total`/`ufs_total`, `last_refresh`), derived from the Gold tables. It
  feeds the frontend `dataStore.meta(id)` seam (provenance comes from the backend,
  not from literals); `implStatus`/`visible` stay as runtime config, documented in
  the contract.
- **BRL/CNY FX via an external source (ECB/Frankfurter) — a yuan column in Gold.**
  The BCB does not publish BRL/CNY (PTAX quotes only 10 currencies, no yuan), so CNY
  is obtained from the ECB reference rates via [Frankfurter](https://frankfurter.dev)
  (free, no key). Monthly seed `extfx_cny_brl` (regenerable with
  `scripts/refresh_cny_seed.py`) → `silver_extfx_currency` (same schema as
  `silver_bcb_currency`) → `silver_currency` (UNION BCB ∪ external). The Gold tables
  now read `silver_currency`, so the `val_*_cny` columns fill again in
  `gold_comex_flows` (100%) **and** `gold_pevs_production` (from ~2005 onward, when
  the ECB CNY data begins). Implied USD/CNY ≈ 6.7 (historically correct).

### Changed
- **Quantities by physical unit family (schema break, no backward
  compatibility).** The fixed `[kg, t, m³, L]` format was removed. Every quantity
  row in Gold now exposes `family` (`massa`|`volume`|`energia`|
  `contagem`|`area`|`desconhecida`), `unit_native` (source label), `qty_native`
  (native value), `qty_base` (converted to the family's base unit) and
  `base_unit` (`t`/`m³`/`MWh`/`un`/`ha`). The conversion happens in **Silver**
  (Gold already delivers the final format). **`gold_pevs_production`** swaps
  `quantity_tons`/`quantity_m3` for these columns; **`gold_comex_flows`** swaps
  `stat_unit`/`stat_unit_symbol`/`statistical_quantity` for
  `unit_native`/`unit_native_symbol`/`qty_native`+`qty_base`+`family`+`base_unit`
  (statistical-unit resolution moved from Gold to Silver;
  `net_weight_kg` remains as a parallel mass-kg). **Rule:** never sum
  `qty_base` across families — every aggregation requires `GROUP BY family` (build
  `q_by_family = {massa:Σt, volume:Σm³, …}` at query time). Monetary value
  remains family-agnostic and summable.
  - New versioned seeds: **`unit_family_conversions`** (unit →
    family + `to_base`, single source — no factor hardcoded in queries) and
    **`product_unit_factors`** (a product→factor crosswalk for commodity units
    like saca/@/bushel/barril, which overrides the generic seed; no row → null
    `qty_base`, flagged for curation — never an invented conversion).
  - `data_quality_flag` reassigned to `(qty, val_brl)`. New curation (warn) test
    `assert_unconvertible_quantities_for_curation` and a
    **dbt unit test** with one case per family + a crosswalk override.
  - ⚠️ **Operational:** `silver_ibge_pevs` is incremental — run
    `dbt build --select silver_ibge_pevs+ --full-refresh` (dev **and** prod) when
    applying this change, otherwise the old partitions are left with the new
    columns null.

### Fixed
- **COMTRADE: resume now identifies the reporter batch by content, not by
  positional index.** The raw object was named `<ano>_r<índice>`, where the index
  came from slicing `list_reporters()` in the order of the UN reference JSON — if
  the UN reordered/changed the reporter set between runs, the same index would map
  to different reporters and resume silently skipped a batch whose composition had
  changed, leaving data never ingested. Now the reporters are **sorted** before
  batching and the basename is a **stable hash** of the batch's codes
  (`<ano>_r<hash>`), with `reporter_codes` recorded in the provenance.
  **Operation:** the first run after this change re-fetches the past years once
  (old basenames become orphaned; Silver dedupes).
- **COMEX/COMTRADE: the delta skip could leave a `(flow,year)`/batch
  permanently missing from Bronze.** When the raw was current, Phase 2 was skipped
  assuming "raw present ⇒ Bronze loaded" — false if a previous run archived the raw
  and aborted before the load. Now a `bronze_loaded_at` marker in the raw object's
  metadata (written after Phase 2; cleared automatically on a re-extract) is the
  source of truth: the skip happens only when the raw is current **and** has
  already been loaded.
- **BCB: the raw basename/provenance reflect the window actually archived.**
  In delta mode each series fetches only its recent overlap window, but the raw
  object was labeled with the configured `bcb_start_year` (e.g. "1980-2026") — a
  window the object does not contain. Now the label derives from the actual range
  of years in the data (`min`/`max` of `reference_date_str`).
- **`pyproject.toml`: license corrected from `MIT` to `Apache-2.0`** (the
  `LICENSE` file and all the other docs were already Apache 2.0); description
  updated to include COMEX/COMTRADE.
- **COMTRADE: ~2.5× double-counting in the Gold values/quantities.** The keyed API
  returns, per `(reporter, partner, cmd, flow)`, a **fully aggregated** record
  (`motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0`) **plus** breakdown
  rows by transport mode / customs / 2nd partner — whose value **sums into the
  aggregate**. Silver kept everything and Gold summed it all together. Fixed by
  keeping only the aggregated record in `silver_comtrade_flows` (lossless: 546,812
  groups = 546,812 rows; Bronze untouched, no re-ingest). Total COMTRADE
  US$1,779bn → US$692bn; the COMEX↔COMTRADE mirror now matches.
- **COMTRADE: wrong physical unit families.** The `comtrade_unit` seed used a
  legacy qtyUnitCode table that does not match the API's codes. Validated against
  the HS6 `standardUnitAbbr`: **5=number of items (count)**, **8=kg
  (mass)**, **12=m³ (volume)** — previously ~24% of rows fell into the wrong family.
- **BCB FX series corrected (affected PEVS and COMEX).** The configured series
  were wrong: `3694` (USD) is **annual** — insufficient for COMEX's monthly
  deflation (it only filled Januaries); `4393` (EUR) returned ~127 and `20542`
  (CNY) ~4 million — **these are not BRL/unit quotes**. Swapped for PTAX **daily
  sell**: `1`=USD, `21619`=EUR (Gold averages by year/month). **CNY was removed** —
  the BCB does not publish BRL/CNY (nor USD/CNY) in the SGS or PTAX; a yuan column
  would require an external source (follow-up). This fixes
  `val_yearfx_{brl,usd,eur}` and `val_real_*_{brl,usd,eur}` in
  `gold_pevs_production` **and** `gold_comex_flows`.
- **`bcb/client`: SGS HTTP 404 treated as a window with no data**, not an error —
  series have different start dates (USD 1984, EUR 1999), so the `--full`
  year-chunking queries windows that predate some series. Previously, a `--full`
  from `BCB_START_YEAR` broke with a 404 on the first empty window.

### Added
- **COMEX reference dimensions — readable labels on `gold_comex_flows`.**
  Three seeds from the MDIC auxiliary tables (`bd/tabelas/`): `comex_unit`
  (`NCM_UNIDADE.csv` → statistical unit, e.g. `16`=METRO CUBICO, `10`=
  QUILOGRAMA LIQUIDO), `comex_country` (`PAIS.csv` → ISO-3 + PT name) and
  `comex_ncm` (`NCM.csv`, filtered for nuts `0801*` + ch. 44 → PT description).
  `gold_comex_flows` gains readable columns via `ref()`: `ncm_description`,
  `country_name`/`country_iso_a3`, `stat_unit`/`stat_unit_symbol` — 100%
  coverage of the current data. Clarifies the quantity semantics: `net_weight_kg`
  is always kg (comparable across products); `statistical_quantity` is in the NCM
  unit (m³ for most wood, kg for nuts) — do not sum across different units.

### Changed
- **Two-phase ingestion with a `raw/` zone — standardized across ALL sources.**
  Every source now follows **extract→raw→bronze**: Phase 1 archives the extract
  *verbatim* in GCS (`raw/<source>/<dataset>/<basename>.parquet`, with provenance
  metadata — URL, ETag/Last-Modified, `fetched_at`, `rows`); Phase 2 reads the
  raw back, filters/shapes it and loads Bronze. Re-filtering, changing
  products/rules or re-deriving Bronze **does not hit the source again** — only a
  real data revision triggers a re-fetch. New primitive `core/raw.py`
  (`land_raw`/`land_raw_file`/`read_raw`/`download_raw`/`list_raw`/`raw_provenance`)
  + `GCS_RAW_PREFIX`.
  - **COMEX:** Phase 1 downloads the full CSV→Parquet (all NCMs) and re-downloads
    **only when the ETag changed** (catching revisions to any year, not just the
    current one); Phase 2 filters the raw via `iter_batches`. `--from-raw`
    re-filters with no internet.
  - **IBGE:** Phase 1 archives the SIDRA response; Phase 2 loads Bronze.
  - **BCB:** each delta window becomes a raw object stamped per run (an
    append-only trail); `--from-raw` rebuilds Bronze by re-reading the trail.
  - Every `embrapa ingest <source>` gains `--from-raw`. The dead primitive
    `core/bronze.land_and_load` was removed (all sources use the new flow).
    Plan: `PLANS/raw_zone_architecture.md`. dbt/Silver/Gold unchanged.

### Added
- **COMEX source (MDIC Comex Stat) — complete Bronze→Silver→Gold pipeline.**
  A new *foreign trade* source (the first of the `flows` form —
  origin→destination), cross-referencing production × trade × FX × inflation of the
  same product. Scope: export **and** import, Brazil nut (NCM `08012100`/
  `08012200`) + the entire chapter 44 (wood/charcoal), at the month×NCM×country×UF
  grain.
  - **Bronze (`src/embrapa_commodities/comex/`):** `client.py` bulk-downloads the
    annual CSVs from Comex Stat (`EXP_<ano>.csv`/`IMP_<ano>.csv`; `;`/latin-1)
    — *stream to disk* (100+ MB files), pandas parse in chunks, column-precise
    filter on `CO_NCM`/`CO_NCM[:2]`. EXP (11 cols) and IMP (13 cols: +
    `VL_FRETE`/`VL_SEGURO`) unified into a schema-union (export writes NULL in the
    two). It does **NOT** use the JSON API (which returned the aggregated Brazil
    total under a malformed filter, HTTP 200). `pipeline.py` has its own `run()`
    with delta by `(flow, year)` (re-fetches the current year, skips years already
    in Bronze). The command `embrapa ingest comex` is multi-chunk (events per
    `(flow, year)` in the monitor); registered in `cli.INGESTS`,
    `doctor.SOURCE_CHECKS` (`_check_comex`) and `doctor.BRONZE_TARGETS`. Config
    `COMEX_*` in `config.py`/`.env.example`.
  - **TLS:** the host `balanca.economia.gov.br` omits the intermediate CA from the
    handshake (`requests`/certifi fails; curl passes via AIA). The public
    intermediate (Sectigo R36) is vendored in `comex/_ca.py` and appended to the
    certifi bundle at runtime — **without disabling verification**.
  - **Silver/Gold (dbt):** `silver_comex_flows` (dedup at the full source grain);
    `gold_comex_flows` (ONE comprehensive `flows` table, grain
    flow×month×NCM×country×UF, aggregation via `GROUP BY` in queries). Applies the
    4 monetary conventions over `VL_FOB` (US$): `val_yearfx_*` at the month FX and
    `val_real_{ipca,igpm,igpdi}_*` (US$→BRL at the month FX → BCB index → today).
  - Coverage: `tests/test_comex_client.py` + `tests/test_comex_pipeline.py`;
    schema tests in `_silver.yml`/`_gold.yml`. Plan in
    `PLANS/comex_flows.md`.
- **Shared Bronze landing primitive (D4).** The identical tail of the Bronze
  pipelines (`ensure_bucket` → Parquet upload → `load_dataframe` with
  partition/cluster keys) was extracted into a source-agnostic primitive,
  analogous to D1 (`core/http.py`): each `run()` keeps only what is specific to the
  source. `ensure_dataset` is left out because the BCB needs the dataset *before*
  the extract (delta lookup). **Note:** this step evolved, still within this
  cycle, into the two-phase ingestion with a `raw/` zone — the final primitive is
  `core/raw.py` (see "Changed" above), not an intermediate
  `core/bronze.land_and_load` (introduced and removed within this same cycle).
  Observable behavior preserved; coverage in `tests/test_core_raw.py`.
- **`core/http.py` — shared HTTP primitives (D1).** A new factory
  `http_retry_policy(transient_exc, deadline_s, max_attempts=5, before_sleep=None)`
  and helper `get_drained(url, *, total_deadline_s, transient_exc, context, ...)`
  encapsulate the tenacity retry policy and the manual body drain under a
  wall-clock deadline (slow-byte defense) that were previously duplicated in the
  IBGE and BCB clients. Shared constants: `DEFAULT_TIMEOUT`, `DEFAULT_HEADERS`,
  `RETRYABLE_STATUS_CODES`. Observable behavior preserved byte for byte —
  source-specific deadlines (75s/180s in IBGE, 60s/120s in BCB) remain in the
  clients; unique defensive logic (IBGE period-halving, BCB year-chunking) also
  did not migrate. Coverage: 11 new tests in
  `tests/test_core_http.py` (including the slow-byte deadline test migrated from
  `test_ibge_client.py`) + 2 "delegate" tests asserting the kwargs passed to
  `get_drained` in each client.
- **Retry observability in the BCB client (D1.1).** `_fetch_window` now wires a
  `before_sleep=_emit_retry` hook into the tenacity policy, symmetric to IBGE —
  SGS series retries now emit a `retry` event
  (`series`, `window`, `attempt`, `reason`) that shows up in `embrapa monitor`.
  Unlike IBGE (which uses a contextvar because the UF lives one frame up), the
  `(code, window)` context comes directly from `retry_state.args`, since
  `_fetch_window` is itself the retried function. Coverage: a test of the hook's
  logic + a regression guard on the wiring (`before_sleep`).

### Changed
- **BCB inflation/currency pipelines collapsed into `bcb/series.py`.** The two
  pipelines were ~90% identical (`_extract`, `_effective_start_year`, `run`);
  they now share a generic SGS series pipeline parameterized by a
  `BcbSeriesSpec` (`kind`, `label_column`, `series_map`, `table`, `schema`, and the
  only genuinely source-specific line — `overlap_start_year(last) -> int`).
  `bcb/inflation.py` and `bcb/currency.py` became thin shims defining their spec
  and delegating. Public entry points (`inflation.run`/`currency.run`),
  constants (`DELTA_OVERLAP_MONTHS`, `BRONZE_SCHEMA`) and observable behavior
  preserved. **Deliberately reverts** the old note in
  `docs/adding_a_data_source.md` ("do not extract `_effective_start_year`"):
  on closer inspection, the difference was one line, today a `Callable` knob. The
  doc was updated to steer SGS series toward the spec, and differently-shaped
  sources toward writing their own `run()`. Tests consolidated: the duplication
  of the two test files became a single `tests/test_bcb_series.py` parameterized
  over the two specs + two thin per-variant files (the spec contract).
- **Gold renamed `gold_commodity_matrix` → `gold_pevs_production`**, adopting the
  `gold_<source>_<form>` convention (`production` for output measurement like PEVS;
  `flows` for origin→destination flow in future trade databases). Reinforces the
  rule of **one comprehensive Gold table per source** (ad-hoc aggregation at
  query time; pre-aggregated marts live in the `serving/` layer — see the
  Pushdown Computing item above).
  **External action required:** repoint the Looker Studio source to
  `gold.gold_pevs_production` and drop the orphaned `gold.gold_commodity_matrix`
  table in prod after the next `make dbt-build-prod` (see `docs/migration_history.md`).

### Fixed
<!-- Bug fixes -->

### Removed
- **Dash + Plotly UI layer removed (2026-05-29).** The frontend is being
  rebuilt with the Claude Design System in a separate flow. The following were
  deleted: the `src/embrapa_commodities/dashboard/` package, the
  `tests/test_dashboard_*` tests, the scripts `scripts/dashboard_*` /
  `scripts/check_dashboard_size.py` / `scripts/dashboard-*.ps1`, the
  `Dockerfile`, the workflow `.github/workflows/dashboard-smoke.yml`, the
  `docs/auth.md` and the Claude Code skills `run-dashboard`,
  `dash-page-scaffold`, `new-chart-component`, `deploy-cloud-run`. The `dashboard`
  and `visual` extras in `pyproject.toml`, the `check-dashboard-size` hook
  in `.pre-commit-config.yaml`, the `--extra dashboard` in `ci.yml` and the
  `dashboard-*` / `test-smoke` targets in the `Makefile` were also removed.
  The backend (Medallion pipeline + dbt + `embrapa` CLI) remains 100%
  functional. The next handoff will join the new design system with
  this backend.

---

## [0.1.0] — 2026-05-26

> Initial release — functional end-to-end Medallion pipeline.

### Added

- **IBGE PEVS ingestion pipeline** via the SIDRA API with support for multiple products and periods.
- **BCB ingestion pipeline** (IPCA/IGP-M/IGP-DI inflation + USD/EUR/CNY FX) via the SGS API.
- **Delta ingestion** for the BCB — only new data is fetched by default.
- **Chunked ingestion** (`ibge-batch --chunk-years`) for large historical windows.
- **Silver layer (dbt)**: typing, dedup, IPCA chain index.
- **Seed `historical_currency_factors`**: absorbs Brazilian currency reforms (1942–1994).
- **Gold layer (dbt)**: `gold_commodity_matrix` table with 22 denormalized columns.
- **Aggregated Gold tables**: `gold_commodity_state_year`, `gold_commodity_year_product`.
- **Unified CLI** with Typer: `embrapa ingest|discover|dbt|doctor|backup-gold`.
- **Web dashboard** with Dash + Plotly (multi-page), deployed via Cloud Run.
- **Multi-stage Dockerfile** with a slim, non-root image, Gunicorn.
- **Service Account Impersonation** (OAuth 2.0) — no distributed keyfiles.
- **Four Service Accounts** with separation of responsibilities (reader, pipeline, dashboard, AI).
- **Gold backup → GCS** (`embrapa backup-gold`, `make dbt-build-prod-with-backup`).
- **`embrapa doctor`**: environment health diagnostics.
- **dev/prod separation** in the dbt schemas with auto-expiration of dev tables (7 days).
- **CI/CD**: GitHub Actions with lint (Ruff), test (pytest), dbt parse.
- **Pre-commit hooks**: gitleaks, ruff, file-hygiene, dashboard size ceiling (500 LOC).
- **Smoke test** of the dashboard with real BQ.
- **Visual check** with Playwright (headless screenshots → `artifacts/`).
- **Cross-platform automated setup**: `setup.sh`, `setup.bat`, `setup.ps1`.
- **Complete documentation**: setup, IAM, auth, cost safety, ownership transfer, testing.

---

<!-- Template for new versions:

## [X.Y.Z] — YYYY-MM-DD

### Added
### Changed
### Fixed
### Removed
### Security
### Deprecated

-->
