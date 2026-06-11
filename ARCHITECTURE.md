# Architecture — Embrapa Commodities Dashboard

> "Under the hood" technical document: folder structure, stack decisions, data flow, and diagrams.

> 📊 **Historical and scientific analysis tool** (Embrapa researchers) — it is not a business-metrics or real-time product; data is processed in batch. Gold is consumed through **two parallel, first-class paths**: (1) **Looker Studio** directly on the Gold table, available now; (2) **dedicated Dash + HTML/CSS dashboard deployed to Cloud Run**, currently being rebuilt with the Claude Design System (the previous Dash UI was removed on 2026-05-29 for a clean handoff). The backend described below is independent of the visualization and already feeds both.

---

## Pipeline Overview

The project implements a **Medallion architecture** (Bronze → Silver → Gold) for historical analysis of Brazilian extractive vegetable production (IBGE PEVS), enriched with FX rates (USD, EUR, CNY) and inflation indices (IPCA, IGP-M, IGP-DI) from Brazil's Central Bank.

```
 ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
 │ IBGE SIDRA │ │  BCB SGS   │ │  BCB SGS   │ │ MDIC COMEX │ │ UN Comtrade  │
 │  (PEVS)    │ │(Inflation) │ │    (FX)    │ │ (bulk CSV) │ │ (API keyed)  │
 └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬───────┘
       │              │              │              │               │
       └──────┬───────┴──────────────┴──────────────┴───────────────┘
              ▼
 ┌─────────────────────────────────────────────────────┐
 │  Python  (src/embrapa_commodities) — two-phase      │
 │  Phase 1  extract → raw/ (verbatim Parquet on GCS)  │
 │  Phase 2  raw/ → filter/shape → BigQuery Bronze     │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  dbt-bigquery  (dbt/)                               │
 │  Silver:  typing, dedup, IPCA chain index           │
 │  Gold:    denormalization, FX, real deflation       │
 │  core:    dim_date, dim_geo_br (conformed)          │
 │  serving: pre-aggregated marts (Pushdown Computing) │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  Consumption (two parallel paths)                   │
 │  • Looker Studio (direct on the Gold table)         │
 │  • Dashboard Dash @ Cloud Run — stateless           │
 │    filters → @param SQL on serving + flask-caching  │
 │    curation: append-only log + SCD Type 2           │
 │    (UI under reconstruction · Claude Design System) │
 └─────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.12 (`pyenv` + `.python-version`) | Mature data ecosystem, modern type hints |
| Package management | `uv` + `uv.lock` | Deterministic resolution, 10–100× faster than pip |
| Build system | `hatchling` | Native PEP 517, zero-config wheel |
| Ingestion | `requests`, `tenacity`, `pandas`, `pyarrow` | Resilient HTTP with retry, native columnar Parquet |
| Data Lake | Google Cloud Storage (Parquet) | Object-store storage, partitioned by source/date |
| Data Warehouse | BigQuery | Serverless, standard SQL, native Looker integration |
| Transforms | `dbt-core` + `dbt-bigquery` | Versioned, testable, incremental transforms |
| CI/CD | GitHub Actions | Lint + test + dbt parse on every PR |
| Lint / Format | Ruff | Replaces flake8 + isort + black; extremely fast |
| SQL Lint | SQLFluff | SQL style validation on the dbt models |
| Pre-commit | gitleaks, ruff, file-hygiene hooks | Credential security + code quality |
| Tests | pytest, responses, pytest-cov | HTTP mocks, coverage, custom markers |
| Configuration | pydantic-settings + `.env` | Typed validation, zero hardcoding |
| Consumption / Visualization | Looker Studio · Dash @ Cloud Run | Two parallel paths over the same Gold tables (see Consumption section) |
| Dashboard data access | `google-cloud-bigquery` + `flask-caching` | Pushdown Computing: UI filters → `@param` SQL on `serving`, cached results |

> The **dedicated visualization** layer (Dash + HTML/CSS, deployed to Cloud Run via Gunicorn) is being rebuilt in the Claude Design System in a separate flow — it is a real target, not abandoned. Looker Studio is the second consumption path and remains available in parallel. When the new frontend arrives via handoff, the UI/deploy stack (Dockerfile, Cloud Run, read-only SA) will be reintroduced and this table updated.

---

## Folder Structure

```
embrapa-dashboard-commodities/
│
├── src/embrapa_commodities/          # Main Python package
│   ├── __init__.py
│   ├── cli.py                        # Typer entrypoint (`embrapa`) + INGESTS registry
│   ├── config.py                     # pydantic-settings — reads .env
│   ├── discover.py                   # Auxiliary helpers (not used in the pipeline)
│   ├── doctor.py                     # Diagnostics + SOURCE_CHECKS / BRONZE_TARGETS registry
│   ├── backup.py                     # Gold snapshot → GCS (introspection via list_tables)
│   ├── monitor/                      # Live progress monitor (`embrapa monitor`)
│   │   ├── state.py                  # State + JSONL event parsing
│   │   └── render.py                 # Rich rendering (progress table)
│   ├── observability.py              # Structured logging
│   │
│   ├── core/                         # ⭐ Shared primitives across sources
│   │   ├── exceptions.py             # SourceTransientError (marker for retry)
│   │   ├── http.py                   # http_retry_policy + get_drained (resilient HTTP)
│   │   └── observability_helpers.py  # pipeline_run (events for embrapa monitor)
│   │
│   ├── gcp/                          # GCP clients
│   │   ├── bigquery.py               # Load Parquet → BQ, auto-create datasets
│   │   └── storage.py                # Upload → GCS, auto-create bucket
│   │
│   ├── serving/                      # ⭐ Dashboard data-access layer (Pushdown)
│   │   ├── sql.py                    # Parameterized SQL (@param) + anti-injection allowlist
│   │   ├── gateway.py                # Cached fetch_* (flask-caching) over the marts
│   │   ├── cache.py                  # flask-caching instance (SimpleCache/Redis)
│   │   ├── iap.py                    # Author via IAP header → edited_by
│   │   └── curation.py               # Append-only SCD2 writer + cache invalidation
│   │
│   ├── ibge/                         # Pipeline IBGE PEVS
│   │   ├── client.py                 # HTTP client SIDRA API
│   │   └── pipeline.py               # Bronze orchestration
│   │
│   ├── bcb/                          # Central Bank pipelines
│   │   ├── client.py                 # SGS API HTTP client
│   │   ├── series.py                 # Generic SGS pipeline (inflation/currency)
│   │   ├── inflation.py              # IPCA/IGP-M/IGP-DI spec
│   │   └── currency.py               # USD/EUR spec (CNY comes from an external, non-BCB source)
│   │
│   ├── comex/                        # MDIC Comex Stat pipeline (bulk CSV)
│   │   ├── client.py                 # CSV downloader (stream to disk + filter)
│   │   ├── pipeline.py               # Bronze orchestration (delta by flow×year)
│   │   └── _ca.py                    # Vendored TLS intermediate CA
│   │
│   └── comtrade/                     # UN Comtrade pipeline (keyed JSON API, global)
│       ├── client.py                 # Keyed GET; key only in the header; enumerates reporters
│       └── pipeline.py               # Bronze chunked/resumable by (year, reporter batch)
│
├── dbt/                              # dbt transforms (Silver + Gold)
│   ├── dbt_project.yml               # dbt project configuration
│   ├── packages.yml                  # Dependencies (dbt_utils)
│   ├── profiles.yml.example          # Profile template (the real one is never committed)
│   ├── models/
│   │   ├── _sources.yml              # Bronze source declarations
│   │   ├── silver/
│   │   │   ├── _silver.yml           # Silver schema + tests
│   │   │   ├── silver_ibge_pevs.sql  # Typed PEVS + dedup (incremental)
│   │   │   ├── silver_bcb_inflation.sql  # IPCA chain index
│   │   │   ├── silver_bcb_currency.sql   # BCB FX (daily USD/EUR PTAX)
│   │   │   ├── silver_extfx_currency.sql # External FX (CNY via ECB/seed)
│   │   │   ├── silver_currency.sql       # UNION BCB ∪ external (read by Gold)
│   │   │   ├── silver_comex_flows.sql    # Typed COMEX + dedup (source grain)
│   │   │   └── silver_comtrade_flows.sql # COMTRADE HS6, 4 regimes; aggregate record only (anti-double-counting)
│   │   ├── gold/
│   │   │   ├── _gold.yml             # Gold schema + tests
│   │   │   ├── gold_pevs_production.sql  # Gold IBGE PEVS (form: production)
│   │   │   ├── gold_comex_flows.sql      # Gold COMEX (form: flows, Brazil)
│   │   │   ├── gold_comtrade_flows.sql   # Gold COMTRADE (form: flows, global bilateral)
│   │   │   ├── gold_commodity_crosswalk.sql  # Cross-source bridge (source,code)→commodity
│   │   │   └── gold_source_metadata.sql  # Per-source provenance (view; dataStore.meta seam)
│   │   │                                 # New sources: gold_<source>_<form>
│   │   ├── core/                     # ⭐ Conformed dimensions (Pushdown Computing)
│   │   │   ├── _core.yml
│   │   │   ├── dim_date.sql          # Calendar (month grain, pt-BR labels)
│   │   │   ├── dim_geo_br.sql        # 27 UFs → name/region/abbrev (N·NE·CO·SE·S)
│   │   │   └── dim_commodity_scd2.sql  # Curation SCD Type 2 (view; gated)
│   │   └── serving/                  # ⭐ Pre-aggregated marts for the Dash dashboard
│   │       ├── _serving.yml
│   │       ├── serving_pevs_annual.sql
│   │       ├── serving_comex_annual.sql
│   │       ├── serving_comex_seasonality.sql
│   │       ├── serving_comtrade_annual.sql
│   │       └── serving_quality_by_source.sql
│   ├── macros/
│   │   ├── generate_schema_name.sql  # Dev/prod schema separation
│   │   ├── safe_numeric.sql          # Safe conversion (IBGE placeholders → NULL)
│   │   ├── data_quality_flag.sql     # OK/MISSING_VALUE/etc. flag
│   │   ├── state_dimensions.sql      # Region/UF lookup
│   │   └── apply_dev_ttl.sql         # Dev table auto-expiration (7 days)
│   ├── seeds/
│   │   ├── _seeds.yml                # Seed schema
│   │   ├── historical_currency_factors.csv  # Currency-reform factors
│   │   ├── comex_unit.csv            # Statistical-unit dimension (CO_UNID)
│   │   ├── comex_country.csv         # Country dimension (CO_PAIS → ISO/name)
│   │   ├── comex_ncm.csv             # NCM dimension (PT description, ch. 08+44)
│   │   ├── comex_via.csv             # Transport-mode dimension (CO_VIA → PT)
│   │   ├── comtrade_country.csv      # M49 → ISO3/name dimension (partnerAreas.json)
│   │   ├── comtrade_unit.csv         # qtyUnitCode → label + family dimension
│   │   ├── comtrade_hs.csv           # HS dimension (0801 + ch. 44; HS.json)
│   │   ├── commodity_crosswalk.csv   # Cross-source bridge (commodity ↔ pevs/ncm/hs6)
│   │   ├── product_unit_factors.csv  # Statistical-unit → base factor (mass/volume) by NCM
│   │   ├── unit_family_conversions.csv  # Unit families and conversions (mass/volume)
│   │   └── extfx_cny_brl.csv         # Monthly BRL/CNY (ECB; scripts/refresh_cny_seed.py)
│   └── tests/                        # Custom dbt tests
│
├── tests/                            # Python tests (pytest)
│   ├── test_cli.py                   # CLI tests
│   ├── test_config.py                # Configuration tests
│   ├── test_ibge_client.py           # IBGE client tests (mocked HTTP)
│   ├── test_ibge_pipeline.py         # IBGE pipeline tests
│   ├── test_bcb_client.py            # BCB client tests
│   ├── test_bcb_series.py            # Generic SGS pipeline tests
│   ├── test_bcb_inflation_pipeline.py
│   ├── test_bcb_currency_pipeline.py
│   ├── test_bcb_pipeline.py
│   ├── test_comex_client.py          # COMEX downloader tests
│   ├── test_comex_pipeline.py        # COMEX pipeline tests (two-phase)
│   ├── test_comtrade_client.py       # UN Comtrade client tests
│   ├── test_comtrade_pipeline.py     # COMTRADE pipeline tests (chunked/resumable)
│   ├── test_core_http.py             # Shared HTTP primitives tests
│   ├── test_core_raw.py              # Raw-zone tests (land/read/provenance/marker)
│   ├── test_gcp_bigquery.py
│   ├── test_gcp_storage.py
│   ├── test_backup.py
│   ├── test_doctor.py
│   ├── test_monitor.py
│   ├── test_observability.py
│   └── test_observability_helpers.py
│
├── scripts/                          # Auxiliary tooling
│   ├── README.md                     # Scripts documentation
│   ├── setup_dev_env.py              # Unified cross-platform setup
│   ├── test_setup.py                 # Setup tests
│   ├── refresh_cny_seed.py           # Updates the extfx_cny_brl.csv seed (ECB)
│   ├── refresh_comtrade_country_seed.py  # Updates the comtrade_country.csv seed (M49)
│   ├── grant-sa-iam-roles.ps1        # IAM roles
│   ├── setup-claude-code-web-sa.sh   # SA for Claude Code Web
│   └── claude-hooks/                 # Security hooks (block-dangerous-commands, protect-secrets)
│
├── docs/                             # Detailed documentation
│   ├── adding_a_data_source.md       # Extension guide: adding a new source
│   ├── auth_architecture.md          # Authentication architecture (Chain of Trust)
│   ├── cost_safety.md                # Budget alert + custom quota
│   ├── frontend_data_contract.md     # Gold → frontend data contract
│   ├── iam_setup.md                  # IAM and Service Accounts setup
│   ├── looker_studio_setup.md        # Looker Studio → Gold connection
│   ├── migration_history.md          # Historical migration notes
│   ├── ownership_transfer.md         # Company handoff checklist
│   ├── setup.md                      # Complete setup guide
│   └── testing.md                    # Testing strategy and guide
│
├── .github/workflows/                # CI/CD
│   ├── ci.yml                        # PR gate: lint + test + dbt parse
│   └── dbt-build-prod.yml            # Automated prod build on push to main
│
├── .claude/                          # Claude Code configuration
│   ├── settings.json
│   └── skills/                       # Skills for Claude Code (backend)
│
├── CLAUDE.md                         # Guide for AI assistants
├── README.md                         # Main documentation
├── ARCHITECTURE.md                   # ← This file
├── pyproject.toml                    # Python manifest (deps, scripts, tools)
├── uv.lock                           # Deterministic lockfile
├── Makefile                          # Development shortcuts
├── LICENSE                           # Apache License 2.0
├── .env.example                      # Environment-variable template
├── .pre-commit-config.yaml           # Pre-commit hooks
├── .python-version                   # Python pin (3.12.11)
├── .gitignore                        # Git exclusions
├── setup.sh / setup.bat / setup.ps1  # Per-platform automated setup
├── test.sh / test.bat                # Testing shortcuts
└── init_dev_env.sh                   # Sandbox initialization
```

> Deleted on 2026-05-29 along with the UI: `src/embrapa_commodities/dashboard/`, `Dockerfile`, `scripts/dashboard*`, `scripts/check_dashboard_size.py`, `tests/test_dashboard_*`, `.github/workflows/dashboard-smoke.yml`, `docs/auth.md`, and the Claude Code skills `run-dashboard` / `dash-page-scaffold` / `new-chart-component` / `deploy-cloud-run`.

---

## Detailed Data Flow

### 0. Raw zone + two-phase ingestion (all sources)

Before Bronze, **every source archives the verbatim extract** at
`gs://<bucket>/raw/<source>/<dataset>/<basename>.parquet` (with provenance
metadata: URL, ETag/Last-Modified, `fetched_at`, `rows`). Bronze derives
from that raw. This way, re-filtering / changing products / re-deriving Bronze
**does not hit the source again** — only a real data revision triggers a re-fetch. Each
`embrapa ingest <source>` has `--from-raw` (rebuilds Bronze from raw, with no
internet). Shared contract in [`core/raw.py`](../src/embrapa_commodities/core/raw.py);
details in [`PLANS/raw_zone_architecture.md`](PLANS/raw_zone_architecture.md).
Per source: COMEX re-downloads only when the ETag changes (filters in Phase 2 via
`iter_batches`); IBGE archives the SIDRA response; BCB archives each delta window
as a per-run stamped object (append-only trail).

### 1. Bronze (raw → BigQuery)

- **Append-only**: each ingestion adds records; it never overwrites.
- All columns are `STRING` except `ingestion_timestamp` — typing happens in Silver.
- **IBGE and BCB are delta by default**: they query the max already in Bronze and fetch only a recent window. BCB: 12-month overlap (inflation) / 30-day overlap (FX). IBGE: from `latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS` forward (absorbing PEVS revisions and picking up a newly published year), instead of re-pulling 1986→today (a huge request that blows the SIDRA slow-byte deadline on an unattended job); cold Bronze → full window. Phase 2 appends what Phase 1 archived.
- Auto-creation: the GCS bucket and BigQuery datasets are created automatically on the first run.

### 2. Silver (dbt, `materialized=table` / `incremental`)

- `silver_ibge_pevs`: **incremental** (`insert_overwrite` by `reference_year`). Dedup via `qualify row_number() ... order by ingestion_timestamp desc`.
- `silver_bcb_inflation`: **table** (needs the full window to compute the IPCA chain index).
- `silver_bcb_currency`: **table** (small table).
- `silver_comex_flows`: **table** (dedup at the full source grain via `qualify`, incl. transport route `CO_VIA`; `safe_numeric` on VL_FOB/KG/QT/freight/insurance). A candidate for incremental if the chapter-44 volume grows over the decades.
- `silver_comtrade_flows`: **table**. Products at the **HS6** level; **4 regimes** (X/M/RX/RM → export/import/re-export/re-import). Keeps **only the fully aggregated record** (`motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0`) — the breakdowns by transport mode/customs/2nd partner **sum into the aggregate**, so re-summing them would double-count (~2.5×). Drops the World partner (`0`); quantity sentinel `0.0` → NULL.
- **Seed `historical_currency_factors`**: a multiplier factor that absorbs Brazilian currency reforms (Cz$ → NCz$ → Cr$ → CR$ → R$). Without it, pre-1994 values are 10⁶–10⁹× inflated.

### 3. Gold (dbt, `materialized=table`)

- IBGE PEVS table: `gold_pevs_production` — one row per `(reference_year, state_acronym, city_name, product_code)`.
- MDIC COMEX table: `gold_comex_flows` — one row per `(flow, reference_year, reference_month, ncm_code, country_code, state_acronym, transport_route_code)` (the transport route `via` is part of the grain; `via_name` via the `comex_via` seed). The 4 currency conventions are applied over `VL_FOB` (US$): `val_yearfx_*` at the registration month's FX, and `val_real_*` converting US$→BRL at the month's FX, deflating by the BCB chain and reconverting at the current FX (**monthly** deflation, not annual, because the grain is monthly).
- UN Comtrade table: `gold_comtrade_flows` — **global** bilateral trade, one row per `(flow, reference_year, reporter_code, partner_code, cmd_code)`. Same 4 conventions over `primaryValue` (US$), but **annual** deflation (year-average FX, year-end inflation index — like PEVS) because the grain is annual. Bilateral geography: `reporter` + `partner` (both M49 → name/ISO3). No double-counting (World dropped in Silver), so `SUM` over partners is the true bilateral total.
- **Cross-source dimension** (an exception to "one table per source"): `gold_commodity_crosswalk` — `(source, code) → commodity_id`, resolved from the `commodity_crosswalk` seed (prefix-based links) against the Gold tables' real codes. Links the same commodity across PEVS/COMEX/COMTRADE for cross analyses.
- **Per-source metadata** (view): `gold_source_metadata` — one row per source with provenance derived from Gold (table, cadence, coverage, counters, `last_refresh`). Feeds the frontend's `dataStore.meta(id)` seam; `implStatus`/`visible` are runtime config (see [docs/frontend_data_contract.md](docs/frontend_data_contract.md)).
- **Gold is per-source, ONE comprehensive table per source.** Naming: `gold_<source>_<form>`, where `<form>` is the semantic grain — `production` (measurement of productive output, no origin→destination; PEVS only) or `flows` (origin→destination flow; the trade databases: COMEX, COMTRADE, NFe). Each source has its own lineage consuming the same deflation/FX Silver tables. Gold is the **comprehensive analytical grain** per source; ad-hoc aggregations (Looker, exploration) come from it via `GROUP BY` at query time. **To enable the Dash dashboard's Pushdown Computing without blowing up cost and latency on BigQuery**, a **`serving/`** layer materializes pre-aggregated marts at the exact chart grains (see [§ Serving Layer](#serving-layer--pushdown-computing-dash-dashboard)) — it **derives** from Gold, it does not replace it. Incompatible grains (monthly × country × HS code for COMEX, event × UF for NFe) also justify separate lineages — see [docs/adding_a_data_source.md](docs/adding_a_data_source.md).
- Four currency conventions (applicable to any monetary Gold table):
  - `val_yearfx_*` — nominal value converted at the year-average FX. NULL for foreign currencies pre-1994.
  - `val_real_{ipca,igpm,igpdi}_*` — value deflated by the IPCA / IGP-M / IGP-DI chain, projected to today. **Use this column for cross-year comparisons.**
- **ER diagram + join guide:** for the entity-relationship map of the Gold tables, the conformed dims, and the serving marts — plus a "how do I join this in Looker?" cheat-sheet — see [docs/gold_data_model.md](docs/gold_data_model.md).

### 4. Consumption

Two parallel paths, both reading the same Gold tables — they are not exclusive and can coexist:

- **Looker Studio** (no-code): direct connection to the Gold tables (`gold.gold_pevs_production`, `gold.gold_comex_flows`). Good for standardized reports and quick exploration without a deploy. Available now.
- **Dedicated dashboard (Dash) on Cloud Run — stateless, Pushdown Computing**: a tailored frontend for researchers (UI being rebuilt with the Claude Design System). It does **not** load Gold tables into memory (Pandas) behind a global lock — that design was dropped due to OOM and concurrency risk. It translates each UI filter into **parameterized SQL** (`@param`) over the **`serving`** layer (pre-aggregated marts), with **flask-caching** on the results; curation uses an **append-only log + SCD Type 2** (see §§ [Serving Layer](#serving-layer--pushdown-computing-dash-dashboard) and [Dynamic Curation](#dynamic-curation--append-only-log--scd-type-2)). The data-access layer (BFF) already lives in [`src/embrapa_commodities/serving/`](../src/embrapa_commodities/serving/); the Dockerfile/Cloud Run and the UI components arrive with the Design System handoff.

---

## `core/` Layer — common contract across sources

`src/embrapa_commodities/core/` concentrates the genuinely shared primitives, keeping IBGE/BCB/… lean:

- **`SourceTransientError`** (in `core/exceptions.py`): a marker for transient upstream failures. `SidraTransientError` and `BcbTransientError` inherit via a mixin, and any new source does the same. This lets the shared decorator `core.http.http_retry_policy` catch all transients without having to list each class by name.
- **`http_retry_policy` + `get_drained`** (in `core/http.py`): the tenacity retry policy (`stop_after_attempt(5) | stop_after_delay(deadline_s)` + `wait_exponential(1, 2, 30)`) and the manual body drain under a wall-clock deadline (a defense against slow-byte hangs that bypass `requests`' per-read timeout). Each source composes it with its own local deadlines and its transient exception. Adopted by `ibge/client._http_get` and `bcb/client._fetch_window`.
- **Raw zone** (in `core/raw.py`): the two-phase ingestion contract — `land_raw(df)` / `land_raw_file(path)` archive the verbatim extract at `raw/<source>/<dataset>/<basename>.parquet` with provenance metadata; `read_raw` / `download_raw` read it back (`download_raw` + `iter_batches` keeps the large-file filter memory-bounded); `list_raw` enumerates a source's trail (for `--from-raw`); `raw_provenance` reads the metadata (the basis of the ETag freshness check). The BQ tail uses `gcp/bigquery.load_dataframe`. Adopted by all sources.
- **`pipeline_run`** (in `core/observability_helpers.py`): a context manager that wraps the event sequence of a single-chunk ingest (`pipeline_start → chunk_start → chunk_end/chunk_error → pipeline_end`). The `ingest ibge`, `ingest bcb-inflation`, and `ingest bcb-currency` commands use the same path, so every single-shot source appears identically in `embrapa monitor`. Multi-chunk flows (`ingest ibge-batch`) emit the per-state/chunk sequence by hand and do **not** use this helper.

Important point: **do not migrate** existing clients (IBGE/BCB) to shared abstractions just for the sake of DRY — the SIDRA slow-byte / period-halving is a hard-won defense that is fine right where it is. The `core/` primitives are adopted consciously, source by source, as appropriate. See the "Deferred items" section of the prep plan.

Does not live in `core/`: source-specific logic (IBGE's per-UF parallelism, BCB's series chunking, etc.) — that stays in `<source>/`.

---

## Serving Layer — Pushdown Computing (Dash dashboard)

> **Architectural pivot (2026-06).** The Dash dashboard does **not** load whole
> Gold tables into memory (Pandas) behind a global `threading.Lock()` — a design
> dropped due to OOM risk and concurrency failures. Cloud Run is
> **stateless**: the UI translates each filter into **parameterized SQL** (`@param`)
> executed by BigQuery, and the (small) result is cached by `flask-caching`.

**Why a `serving/` layer.** Naive pushdown directly on Gold would scan
gigabytes on every filter. To keep cost and latency viable, `dbt/models/serving/`
materializes **pre-aggregated marts at the exact chart grains** (mapped in
[`docs/frontend_data_contract.md`](docs/frontend_data_contract.md)), reducing the
scan from **GB → MB**. They are **tables**, not views: a view over Gold
would re-scan the entire fact on every query and save nothing — the gain comes from
materialized pre-aggregation, partitioned by year and clustered by the filters.

| Mart (`serving`) | Grain | Feeds |
|---|---|---|
| `serving_pevs_annual` | year × UF × produto × família | overviewTS · productTS · ufData (PEVS) |
| `serving_comex_annual` | year × flow × NCM × UF × country | overview · produto · UF · partner · flow (COMEX) |
| `serving_comex_seasonality` | year × month × flow × NCM | monthlyData / sazonalidade |
| `serving_comtrade_annual` | year × flow × cmd × reporter × partner | partner · flow · market-share (COMTRADE) |
| `serving_quality_by_source` | source × data_quality_flag | quality donut |

**Conformed dimensions** (`dbt/models/core/`): `dim_date` (month grain, pt-BR
labels, quarter/semester) and `dim_geo_br` (27 UFs → name / region / abbreviation
N·NE·CO·SE·S) are the **single source** of the serving joins. They live in the Gold dataset
(they are *build* inputs baked into the marts, not read live by the UI). The marts
carry `commodity_id` (via `gold_commodity_crosswalk`) for the live LEFT JOIN
with the curation dimension.

**Own dataset + least privilege.** The marts live in the `serving` dataset
(`BQ_SERVING_DATASET`), separate from Gold, so that the dashboard's SA
(`sa-web-dashboard-prod`) is scoped **only** to the serving surface.

**Data-access layer (Python).** [`src/embrapa_commodities/serving/`](../src/embrapa_commodities/serving/)
is the **UI-agnostic** BFF that Dash imports — **no pages/charts** (those arrive
with the Design System handoff):

- `sql.py` — builders for **parameterized** SQL (`@param`); the measure column
  (which cannot be a bind param) goes through an **allowlist** against injection.
- `gateway.py` — **cached** `fetch_*` functions (`@cache.memoize()`) that run the
  marts. No global Pandas DataFrame, no lock — the state lives in BigQuery.
- `cache.py` — `flask-caching` instance. **Multi-instance on Cloud Run is free
  with `SimpleCache`:** the marts converge within the TTL (overnight data) and the
  classification read uses a short TTL (`CACHE_CLASSIFICATION_TIMEOUT`, 30s)
  that bounds the staleness across instances — the one that edits invalidates immediately, the
  others converge within ≤30s. `CACHE_TYPE=RedisCache` (Memorystore) is **optional**,
  only for instant cross-instance consistency under high traffic.
- `iap.py` — extracts the author from the **IAP** header (`edited_by`).
- `curation.py` — the append-only curation writer (below).

**Cache policy.** Marts change **only** in the overnight dbt rebuild → cache by
**TTL** (`CACHE_DEFAULT_TIMEOUT`). The curation classification **can** change
between rebuilds → cache **explicitly invalidated** on write **+ short TTL**
(`CACHE_CLASSIFICATION_TIMEOUT`, 30s): the invalidation resolves the instance that
writes; the short TTL resolves the others (eventual consistency ≤30s) — this is what
allows scaling to several instances **without Redis**.

---

## Dynamic Curation — append-only log + SCD Type 2

Researchers reclassify commodities (processing stage: `in_natura`,
`beneficiado`, `semi_processado`, `industrializado`, …) through the curation panel.
The flow **never overwrites Gold**:

1. **Write ("Save" button).** `serving.curation.record_processing_stage` appends
   **one immutable row** to `research_inputs.commodity_processing_stage_log` (a
   parameterized `INSERT` DML — consistent for immediate read). The author comes from the
   **IAP** header `X-Goog-Authenticated-User-Email` into the `edited_by` column — every
   edit is attributable to a person, never to the Service Account. Then the
   classification cache is invalidated. The table is **auto-created**
   (`ensure_curation_log_table`, the house pattern).
2. **History (SCD Type 2).** The `dim_commodity_scd2` view (`dbt/models/core/`)
   derives, per commodity, `valid_from` / `valid_to` / `is_current` via
   `lead(edited_at)` over the log. It is a **view**, not a table: a new `INSERT`
   appears to the UI **immediately**, with no dbt rebuild. It is gated by
   `--vars 'enable_curation: true'` (enable it once the log exists, so the default
   build stays green until then).
3. **Read (UI).** The dashboard performs a **live LEFT JOIN** between the **static
   Serving View** (heavy, pre-aggregated mart, with `commodity_id`) and the
   **live** `dim_commodity_scd2` (light), filtering `is_current` for "now" — or
   `valid_from <= as_of < valid_to` to reconstruct how the commodity was
   classified at a past date (traceability).

```
"Save"   ─► INSERT append-only ─► research_inputs.commodity_processing_stage_log
                                              │  (lead() → valid_from/valid_to/is_current)
                                              ▼
   Serving mart (static)       ──live LEFT JOIN──►  dim_commodity_scd2 (view)
   by commodity_id                                   is_current = true
```

---

## Extension points for adding sources

Adding a new source touches three lightweight registries + creating two files. Everything is documented in [docs/adding_a_data_source.md](docs/adding_a_data_source.md). The registries are:

- `cli.INGESTS` (`src/embrapa_commodities/cli.py`) — registers the source in `embrapa ingest all`.
- `doctor.SOURCE_CHECKS` (`src/embrapa_commodities/doctor.py`) — adds the `embrapa doctor` probe for the new API.
- `doctor.BRONZE_TARGETS` (`src/embrapa_commodities/doctor.py`) — makes the "does the Bronze table exist?" check include the new table.

Each `@ingest_app.command()` stays hand-maintained (heterogeneous observability across sources — IBGE emits state events, BCB does not). Only `ingest all` uses the registry.

---

## Dev / Prod Separation

The `generate_schema_name.sql` macro ensures:

| Target | Silver Dataset | Gold Dataset |
|---|---|---|
| `dev` (default) | `dbt_dev_silver` | `dbt_dev_gold` |
| `prod` | `silver` | `gold` |

Dev tables auto-expire in **7 days** (the `apply_dev_ttl` macro).

---

## Configuration Model

**Nothing is hardcoded.** All parameters flow via `.env` → `pydantic-settings` (`config.py`):

- GCS bucket, prefixes, dataset names
- IBGE product codes, BCB series
- GCP project, BQ location
- Authentication method (impersonation vs. keyfile)

Transferring to another GCP project = copy `.env.example`, adjust, and run `embrapa ingest all`.

---

## Security and Authentication

A **Service Account Impersonation** model (OAuth 2.0) with no distributed keyfiles:

- **`sa-secret-reader-prod`**: impersonation target for developers (dbt + queries)
- **`sa-data-pipeline-prod`**: ingestion pipelines (write GCS + BQ)
- **`sa-ai-agent-admin-prod`**: AI agents (BQ editor + GCS)

> The `sa-web-dashboard-prod` SA is the **runtime of the stateless dashboard on Cloud Run**. With Pushdown Computing it is scoped to **least privilege**: `roles/bigquery.dataViewer` **only on the `serving` dataset** (marts + `dim_commodity_scd2`) — not on all of Gold — plus `roles/bigquery.jobUser` (project-level) to run the queries, and `roles/bigquery.dataEditor` **only on the `research_inputs` dataset** for the append-only curation `INSERT`. The dashboard sits **behind IAP** as a **hard deploy requirement** — the Service is published with `--ingress internal-and-cloud-load-balancing` + `--no-allow-unauthenticated` behind a Load Balancer with IAP enabled, so that the `X-Goog-Authenticated-User-Email` header (the source of the auditable `edited_by`) cannot be forged. Details and the rationale for each flag in [`docs/auth_architecture.md` § Dashboard ingress](docs/auth_architecture.md#dashboard-ingress--iap-behind-a-load-balancer-hard-requirement). It is dormant while the UI is rebuilt in the Claude Design System. **Looker Studio does not use this SA** — it consumes Gold via the end user's OAuth (an independent consumption path).

Full details in [`docs/auth_architecture.md`](docs/auth_architecture.md) and [`docs/iam_setup.md`](docs/iam_setup.md).

---

## CI/CD

### GitHub Actions (`ci.yml`)

Runs on every PR to `main`:
1. `make lint` — Ruff check + format
2. `make test` — pytest (no GCP credentials)
3. `dbt deps` + `dbt parse` — Jinja + ref/source validation without a warehouse

### dbt build prod (`dbt-build-prod.yml`)

A push to `main` that touches `dbt/**` or `config.py` triggers a prod Silver/Gold build via Workload Identity Federation. Gold snapshots remain manual (`make dbt-build-prod-with-backup` locally, before release boundaries).

---

## Ingestion orchestration (Cloud Run Job + Cloud Scheduler)

The `embrapa ingest all` CLI is packaged as a **Cloud Run Job** — **not** a
Service. The distinction is deliberate:

| | **Job** (ingestion) | **Service** (Dash dashboard) |
|---|---|---|
| Nature | batch, ephemeral — runs to completion and stops | stateless, always-on, scales to zero |
| HTTP port | no | yes (Gunicorn) |
| Trigger | **Cloud Scheduler** (cron) | user request (behind IAP) |

A **Cloud Scheduler** triggers the Job **overnight** (e.g., a daily cron at a
low-contention time, outside the analysis window). Unattended
execution is safe because the current resilience already absorbs the
typical failures of a public source:

- **`tenacity`** via `core.http.http_retry_policy` (`stop_after_attempt(5)` +
  `wait_exponential` + drain under a wall-clock deadline) re-absorbs transients
  (HTTP 5xx, timeouts, slow-byte).
- **IBGE and BCB are delta by default** — IBGE re-fetches only recent years (from
  `latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS`), BCB uses an overlap window;
  COMEX re-downloads only when the ETag changes; COMTRADE is resumable by daily quota.
  No leg re-pulls the entire history — re-running the Job is idempotent
  enough for a blind cron.
- A total failure emits an event (the basis for the ROADMAP's failure notification).

> **Artifacts** in [`deploy/ingestion/`](deploy/ingestion/): `Dockerfile` (the Job's
> image — distinct from the dashboard *Service*'s Dockerfile), `cloudbuild.yaml`,
> `deploy.sh` (build + create/update the Job by reading the `.env`) and `schedule.sh` (create/
> update the Scheduler trigger). Shortcuts: `make ingest-job-deploy` and
> `make ingest-job-schedule`. The actual deploy (running the scripts in the GCP project) is
> an operator step — the backend they invoke (`embrapa ingest all`) is already
> ready and is the same path tested locally.

---

## Related Documentation

A complete index of all project documentation (root + `docs/`) is available in the [`README.md`](README.md#-documentation).
