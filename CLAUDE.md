# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and other AI assistants when working with code in this repository.

## Project Overview

**Embrapa Commodities Dashboard** — Medallion pipeline (Bronze → Silver → Gold) for historical analysis of Brazilian extractive vegetable production (IBGE PEVS), enriched with FX rates (USD, EUR, CNY) and inflation indices (IPCA, IGP-M, IGP-DI) from Brazil's Central Bank.

Built for **Embrapa researchers** — the purpose is historical/scientific exploration of time series, **not** business metrics or real-time analytics (data is ingested and transformed in batch).

- **Language**: Python 3.12 · **Package manager**: uv · **Build**: hatchling
- **Data transforms**: dbt-core + dbt-bigquery
- **Infrastructure**: GCS + BigQuery + GitHub Actions
- **Consumption (two parallel paths)**: Looker Studio (no-code, direct on Gold) · custom Dash + HTML/CSS dashboard deployed to Cloud Run (under reconstruction). Both read the same Gold tables; neither is exclusive.
- **License**: Apache 2.0

> ⚠️ **Frontend em reconstrução com Claude Design System.** The custom Dash dashboard (deployed to Cloud Run) was removed on 2026-05-29 for a clean handoff and its **UI** is being rebuilt in a separate flow. It is **one of two first-class consumption paths** — the other is Looker Studio, which connects directly to Gold and works today. **Cloud Run is a real deploy target, not abandoned.** As of the **2026-06 Pushdown Computing pivot**, the dashboard's **data-access layer is built here** (the old in-memory/Pandas design was dropped): `dbt/models/serving/` (pre-aggregated marts), `dbt/models/core/` (conformed dims + the SCD2 curation view), and `src/embrapa_commodities/serving/` (the UI-agnostic BFF: parameterized BigQuery queries, `flask-caching`, the append-only curation writer with IAP author capture). Guardrail: **still do not preemptively scaffold the Dash UI itself — pages, layouts, chart components, `app.py`, or the dashboard's Cloud Run *Service*/Dockerfile** — those arrive with the design-system handoff; build them only when the user explicitly asks. (Note: the *ingestion* Cloud Run **Job** image is a separate, already-built artifact under `deploy/ingestion/` — batch, no UI; don't confuse it with the dashboard Service.)

## Documentation Map

| File | Purpose |
|------|---------|
| `README.md` | Human entry point, quickstart, CLI reference |
| `ARCHITECTURE.md` | Technical deep-dive: folder structure, data flow, stack decisions |
| `CONTRIBUTING.md` | Commit conventions, branch flow, PR process |
| `CHANGELOG.md` | Version history (Keep a Changelog format) |
| `TODO.md` | Macro task list (done + pending) |
| `ROADMAP.md` | Short/medium/long-term project vision |
| `SECURITY.md` | Vulnerability reporting policy |
| `PLANS/` | Detailed feature plans (one .md per feature) |
| `docs/` | Deep-dive docs (setup, IAM, testing, cost safety, etc.) |

## Code Style

- **Formatter/Linter**: Ruff (line-length=100, target=py312)
- **Rules**: E, F, I, B, UP, SIM, RUF (ignoring RUF001-003 for pt-BR Unicode)
- **Docstrings**: Portuguese (technical comments may be in English)
- **SQL**: SQLFluff for dbt models
- **Pre-commit**: gitleaks + ruff + file-hygiene hooks (install with `make precommit-install`)

## Commands

Setup (once per machine):
```bash
pyenv local 3.12.11 && uv sync
gcloud auth application-default login
cp .env.example .env                          # then edit GCP_PROJECT_ID etc.
cp dbt/profiles.yml.example ~/.dbt/profiles.yml
make precommit-install                        # optional: ruff + file-hygiene on every commit
```

Ingestion (Python → GCS Parquet → BigQuery Bronze):
```bash
make ingest-all                               # IBGE + both BCB series + COMEX (BCB = delta; COMTRADE is key-gated, excluded)
make ingest-ibge-historical                   # auto-chunked for large year windows
uv run embrapa ingest {ibge|bcb-inflation|bcb-currency|all}
uv run embrapa ingest bcb-inflation --full    # force refetch from BCB_START_YEAR
uv run embrapa ingest ibge-batch --chunk-years 5
```

**BCB pipelines are delta by default**: they query `max(reference_date_str)`
already in Bronze for each series and only fetch from a small overlap window
forward (12 months for inflation, 30 days for FX) — this absorbs BCB
revisions of preliminary readings without re-pulling the whole history.
Use `--full` after schema changes or to backfill a new series.

Cold-storage backup of the prod Gold tables. **The recommended prod path
bundles build + snapshot in one target — reach for this instead of bare
`dbt-build-prod` whenever the run is preservation-worthy:**

```bash
make dbt-build-prod-with-backup   # build prod, then snapshot Gold to GCS
make backup-gold                  # snapshot only (after an existing prod build)
uv run embrapa backup-gold        # same as above, direct CLI form
```

Each snapshot lands at `gs://${GCS_BUCKET}/backups/run=<ts>/...`. Plain
`make dbt-build-prod` is intentionally left un-chained so throwaway prod
experiments don't accumulate snapshots. **Operator responsibility:** run
`dbt-build-prod-with-backup` at least once per release boundary (after
schema changes, new product codes, or anything you'd want to roll back
to). `embrapa doctor` warns if the latest snapshot is more than
`BACKUP_STALENESS_DAYS` (default 14) old, and fails clearly if no
snapshot exists.

dbt transforms (run from repo root via Makefile, or `cd dbt` to call dbt directly):
```bash
make dbt-build           # dev target — writes to dbt_dev_silver, dbt_dev_gold
make dbt-build-prod      # prod target — writes to silver, gold (full-refresh)
make dbt-test
cd dbt && uv run dbt run --select silver_ibge_pevs+    # single model + downstream
cd dbt && uv run dbt test --select gold_pevs_production
cd dbt && uv run dbt build --full-refresh              # force rebuild incremental models
```

**`silver_ibge_pevs` is incremental** (insert_overwrite by `reference_year`).
Each `dbt build` scans only Bronze partitions for years with new ingestions —
the dedup `qualify` no longer pulls the whole Bronze history. Use
`--full-refresh` after schema changes, after dropping the table, or when
re-anchoring to a different `ingestion_timestamp` baseline. `silver_bcb_*`
remain `materialized=table` (small tables; the IPCA chain index requires a
full-series window).

Discovery helpers (auxiliary — for filling in `.env`, not part of the pipeline):
```bash
uv run embrapa discover ibge-periods   --table-id 289
uv run embrapa discover ibge-products  --keywords castanha,madeira
uv run embrapa discover bcb-series     433
```

Lint / test:
```bash
make lint                                # ruff check + ruff format --check
make test                                # pytest
uv run pytest tests/test_ibge_client.py::test_name   # single test
```

## Architecture

Medallion pipeline: data sources (today IBGE PEVS + BCB SGS; see `cli.INGESTS` registry — extensible) → Python (Bronze) → dbt (Silver → Gold) → consumed in parallel by **Looker Studio** (direct) and the **custom Dash/Cloud Run dashboard** (under reconstruction).

For the full technical deep-dive (folder structure, data flow diagrams, stack decisions, Bronze/Silver/Gold details, configuration model, dev/prod separation), see [`ARCHITECTURE.md`](ARCHITECTURE.md).

Key facts for AI context:
- **Bronze is append-only**; Silver dedupes on natural key by `ingestion_timestamp desc`.
- All Bronze columns are `STRING` except `ingestion_timestamp`.
- The seed `historical_currency_factors` absorbs currency reforms; without it, pre-1994 values are 10⁶–10⁹× too large.
- `val_real_{ipca,igpm,igpdi}_*` columns are for cross-year comparison; `val_yearfx_*` are nominal.
- Config flows through `src/embrapa_commodities/config.py` (pydantic-settings + `.env`). `BCB_INFLATION_SERIES` uses `CODE:LABEL,CODE:LABEL` format — keep `BCB_INFLATION_SERIES_IPCA_CODE` / `BCB_INFLATION_SERIES_IGPM_CODE` / `BCB_INFLATION_SERIES_IGPDI_CODE` in sync (dbt reads each via `env_var()` to wire the right series into the Gold pivot).
- `target=dev` → `dbt_dev_silver` / `dbt_dev_gold` (auto-expire 7 days). `target=prod` → `silver` / `gold`.
- **Adding a new data source**: follow [`docs/adding_a_data_source.md`](docs/adding_a_data_source.md). The registries that need new entries: `cli.INGESTS`, `doctor.SOURCE_CHECKS`, `doctor.BRONZE_TARGETS`. Shared primitives live in `src/embrapa_commodities/core/`. **Gold is per-source, ONE comprehensive table per source** named `gold_<source>_<form>` (`<form>` = `production` for output measurement like PEVS, or `flows` for origin→destination trade like COMEX/COMTRADE/NFe). Ad-hoc aggregations (Looker, exploration) come from `GROUP BY` at query time on Gold; **for the Dash dashboard's Pushdown Computing, the `serving/` layer materializes pre-aggregated marts** at the exact chart grains (fed by the conformed dims `dim_date`/`dim_geo_br` in `core/`) — they derive from Gold, not replace it (see `ARCHITECTURE.md` § Camada Serving). `gold_pevs_production` is the PEVS table.

## Skills available

Each skill in `.claude/skills/` provides deep context for a specific workflow. Claude Code loads them on demand by matching the task description.

| Skill | When to use |
|-------|------------|
| `dbt-workflow` | Create/modify dbt models, run transforms, understand Silver/Gold patterns |
| `lint-and-test` | Run ruff, pytest, sqlfluff, or pre-commit hooks |
| `ingest-data` | Ingest from IBGE/BCB, add products or series, debug pipelines |
| `bigquery-debug` | Debug BQ errors (404/403/400), inspect data, diagnostic queries |
| `code-audit` | Strategic health audit: complexity, maintainability, coverage (run periodically, not on every change) |

> The frontend-specific skills (`run-dashboard`, `dash-page-scaffold`, `new-chart-component`, `deploy-cloud-run`) were removed alongside the old Dash UI. New UI-related skills will be (re)introduced as part of the Claude Design System handoff.

## Migration history

One-time migration notes (Bronze re-partitioning, Gold schema changes, column renames) are archived in `docs/migration_history.md`.
