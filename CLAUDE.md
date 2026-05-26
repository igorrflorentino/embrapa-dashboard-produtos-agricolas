# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
make ingest-all                               # IBGE + both BCB series (BCB = delta)
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
cd dbt && uv run dbt test --select gold_commodity_matrix
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

Medallion pipeline ingests IBGE PEVS (extractive vegetable production) plus BCB SGS (inflation + FX) and emits a single denormalized Gold table for Looker Studio:

```
IBGE SIDRA  ─┐
BCB SGS     ─┼─► Python (src/embrapa_commodities) → GCS Parquet (landing/)
             ┘                                           │
                                                         ▼
                              dbt-bigquery → Silver (typed + IPCA chain)
                                                         │
                                                         ▼
                                        gold.gold_commodity_matrix
```

**Bronze (Python).** `src/embrapa_commodities/cli.py` is the single Typer entry point. Each pipeline (`ibge/pipeline.py`, `bcb/inflation.py`, `bcb/currency.py`) fetches → writes Parquet to `gs://${GCS_BUCKET}/${GCS_LANDING_PREFIX}/...` → loads with `WRITE_APPEND` into BigQuery. **Bronze is append-only**; every Silver model dedupes on the natural key ordered by `ingestion_timestamp desc`. All Bronze columns are `STRING` except `ingestion_timestamp`. `gcp/bigquery.py` and `gcp/storage.py` auto-create datasets and the bucket on first run, so no infra is provisioned outside the code.

**Silver (dbt, materialized=table).** Three models in `dbt/models/silver/`. One reference seed in `dbt/seeds/` carries domain knowledge that cannot be derived from source data:

- `historical_currency_factors` — date-aware multiplier that absorbs both the "Mil" multiplier and cumulative Brazilian currency reforms (Cz$ → NCz$ → Cr$ → CR$ → R$). The name "Mil Cruzeiros" was reused for three distinct currencies (1942, 1970, 1990), so the seed joins on `(unit_of_measure, reference_year BETWEEN year_from AND year_to)`. **Without this factor, pre-1994 values are 10⁶–10⁹× too large** because the IPCA chain captures inflation only, not reform divisions.

Product codes are taken directly from SIDRA's `tipo_de_produto_extrativo_codigo` column — no mapping seed is required.

**Gold (dbt, materialized=incremental, insert_overwrite partitioned by reference_year).** Single model `gold_commodity_matrix` produces 22 columns per `(reference_year, state_acronym, city_name, product_code)`. Two monetary conventions matter:

- `val_yearfx_*` — `val_raw` (in current BRL numerary, no inflation correction) divided by that year's average FX rate. Foreign-currency columns are NULL pre-1994 to avoid mixing old Cruzeiros with current USD/EUR/CNY. Historical auditing only.
- `val_real_{ipca,igpm}_*` — value projected to today via the chain-linked IPCA/IGP-M index, then optionally converted at today's FX. **Use this column for cross-year comparison.**

The IPCA chain (in `silver_bcb_inflation.sql`) compounds SGS 433's monthly percent change into a 100-base index via `100 * exp(sum(log(1 + pct/100)) over (...))`. SGS 433 shows no spike at reform dates — that's why the currency factor seed must be applied in Silver *before* the chain index is used in Gold.

## Configuration model

Nothing is hardcoded — bucket, prefixes, dataset names, table names, IBGE product codes, BCB series codes all flow through `src/embrapa_commodities/config.py` (pydantic-settings reading `.env`). This is intentional for ownership transfer (see `docs/ownership_transfer.md`): copying `.env.example` to a new GCP project and running `embrapa ingest all` rebuilds the entire infrastructure.

`BCB_INFLATION_SERIES` and `BCB_CURRENCY_SERIES` use `CODE:LABEL,CODE:LABEL` format. If you change these keys, also update `BCB_INFLATION_SERIES_IPCA_CODE` and `BCB_INFLATION_SERIES_IGPM_CODE` in `.env` — `dbt_project.yml` reads them via `env_var()` and the Gold model uses them to pick the right series for the `val_real_*` projections.

## dev / prod schema separation

`dbt/macros/generate_schema_name.sql` enforces:
- `target=dev` (default) → `dbt_dev_silver`, `dbt_dev_gold` (sandboxed)
- `target=prod` → `silver`, `gold` (no prefix)

Always iterate on `make dbt-build` (dev). `make dbt-build-prod` does a `--full-refresh` against the real datasets — only run after dev validation.

**Dev schemas auto-expire after 7 days.** The `apply_dev_ttl` macro runs as an `on-run-end` hook only when `target.name == 'dev'`, setting `default_table_expiration_days = 7` on `dbt_dev_silver` and `dbt_dev_gold`. Abandoned experimentation tables self-clean instead of accumulating in the project.

## Skills available

Each skill in `.claude/skills/` provides deep context for a specific workflow. Claude Code loads them on demand by matching the task description.

| Skill | When to use |
|-------|------------|
| `run-dashboard` | Run, serve, smoke-test, or screenshot the Dash web app |
| `dbt-workflow` | Create/modify dbt models, run transforms, understand Silver/Gold patterns |
| `dash-page-scaffold` | Create a new page or view in the dashboard |
| `deploy-cloud-run` | Deploy to Cloud Run, build Docker image, verify production |
| `lint-and-test` | Run ruff, pytest, sqlfluff, or pre-commit hooks |
| `ingest-data` | Ingest from IBGE/BCB, add products or series, debug pipelines |
| `bigquery-debug` | Debug BQ errors (404/403/400), inspect data, diagnostic queries |
| `new-chart-component` | Create new Plotly chart types or Dash components |
| `code-audit` | Strategic health audit: complexity, maintainability, coverage (run periodically, not on every change) |

## Migration history

One-time migration notes (Bronze re-partitioning, Gold schema changes, column renames) are archived in `docs/migration_history.md`.
