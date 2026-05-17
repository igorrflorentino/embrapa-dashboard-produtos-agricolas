# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Setup (once per machine):
```bash
pyenv local 3.12.11 && uv sync
gcloud auth application-default login
cp .env.example .env                          # then edit GCP_PROJECT_ID etc.
cp dbt/profiles.yml.example ~/.dbt/profiles.yml
```

Ingestion (Python → GCS Parquet → BigQuery Bronze):
```bash
make ingest-all                               # IBGE + both BCB series
make ingest-ibge-historical                   # auto-chunked for large year windows
uv run embrapa ingest {ibge|bcb-inflation|bcb-currency|all}
uv run embrapa ingest ibge-batch --chunk-years 5
```

dbt transforms (run from repo root via Makefile, or `cd dbt` to call dbt directly):
```bash
make dbt-build           # dev target — writes to dbt_dev_silver, dbt_dev_gold
make dbt-build-prod      # prod target — writes to silver, gold (full-refresh)
make dbt-test
cd dbt && uv run dbt run --select silver_ibge_pevs+    # single model + downstream
cd dbt && uv run dbt test --select gold_commodity_matrix
```

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

**Silver (dbt, materialized=table).** Three models in `dbt/models/silver/`. Two reference seeds in `dbt/seeds/` carry domain knowledge that cannot be derived from source data:

- `ibge_product_codes` — maps IBGE classification-193 codes (from `.env`) to the product_description string SIDRA returns. **When you add/remove a product code in `.env`, this seed must be updated.**
- `historical_currency_factors` — date-aware multiplier that absorbs both the "Mil" multiplier and cumulative Brazilian currency reforms (Cz$ → NCz$ → Cr$ → CR$ → R$). The name "Mil Cruzeiros" was reused for three distinct currencies (1942, 1970, 1990), so the seed joins on `(unit_of_measure, reference_year BETWEEN year_from AND year_to)`. **Without this factor, pre-1994 values are 10⁶–10⁹× too large** because the IPCA chain captures inflation only, not reform divisions.

**Gold (dbt, materialized=incremental, insert_overwrite partitioned by reference_year).** Single model `gold_commodity_matrix` produces 22 columns per `(reference_year, state_acronym, city_name, product_code)`. Two monetary conventions matter:

- `valnominal*` — value of the year converted at that year's FX rate. Historical auditing only.
- `valreal{ipca,igpm}*` — value projected to today via the chain-linked IPCA/IGP-M index, then optionally converted at today's FX. **Use this column for cross-year comparison.**

The IPCA chain (in `silver_bcb_inflation.sql`) compounds SGS 433's monthly percent change into a 100-base index via `100 * exp(sum(log(1 + pct/100)) over (...))`. SGS 433 shows no spike at reform dates — that's why the currency factor seed must be applied in Silver *before* the chain index is used in Gold.

## Configuration model

Nothing is hardcoded — bucket, prefixes, dataset names, table names, IBGE product codes, BCB series codes all flow through `src/embrapa_commodities/config.py` (pydantic-settings reading `.env`). This is intentional for ownership transfer (see `docs/ownership_transfer.md`): copying `.env.example` to a new GCP project and running `embrapa ingest all` rebuilds the entire infrastructure.

`BCB_INFLATION_SERIES` and `BCB_CURRENCY_SERIES` use `CODE:LABEL,CODE:LABEL` format. If you change these keys, also override the `inflation_series_ipca` / `inflation_series_igpm` vars in `dbt/dbt_project.yml`, which the Gold model uses to pick the right series.

## dev / prod schema separation

`dbt/macros/generate_schema_name.sql` enforces:
- `target=dev` (default) → `dbt_dev_silver`, `dbt_dev_gold` (sandboxed)
- `target=prod` → `silver`, `gold` (no prefix)

Always iterate on `make dbt-build` (dev). `make dbt-build-prod` does a `--full-refresh` against the real datasets — only run after dev validation.

## Notes for changes

- Adding an IBGE product: update `IBGE_PRODUCT_CODES` in `.env` *and* `dbt/seeds/ibge_product_codes.csv`. A `not_null` test on Gold `product_code` will fail loudly if the seed is out of sync.
- Adding a new historical-currency unit string (e.g. older IBGE labels): add a row to `dbt/seeds/historical_currency_factors.csv` with a non-overlapping `[year_from, year_to]` range.
- IBGE SIDRA has a per-request cell limit. For windows >10 years use `ingest ibge-batch`; chunk size auto-scales with number of products (`recommended_chunk_years` in `ibge/client.py`).
- Tests mock HTTP clients via `responses` — see `tests/test_ibge_client.py` and `tests/test_bcb_client.py` for the pattern.
