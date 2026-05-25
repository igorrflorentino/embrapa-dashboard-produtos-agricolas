# Migration History

These are one-time migration notes from past schema changes. They are kept for historical reference only and are not part of the active development workflow.

## Bronze re-partitioning

Bronze tables are now partitioned by `DATE(ingestion_timestamp)` and clustered (IBGE: `municipio_codigo, ano, variavel_codigo`; BCB: `series_code, reference_date_str`). BigQuery cannot retrofit partitioning on existing tables — if you have pre-existing Bronze tables from before this change, drop them before the next `embrapa ingest *` run, otherwise the load job fails with a partition mismatch:

```bash
bq rm -f -t "${GCP_PROJECT_ID}:bronze_ibge.sidra_t289_raw"
bq rm -f -t "${GCP_PROJECT_ID}:bronze_bcb.inflation_series_raw"
bq rm -f -t "${GCP_PROJECT_ID}:bronze_bcb.currency_series_raw"
```

## Gold materialization

Changed from `incremental` to `table`. No action required — `dbt build` will recreate it cleanly. The Gold model now also has new columns (`reference_date`, `state_name`, `region`, `city_code`, `last_refresh`) and renamed columns (snake_case throughout). Looker Studio reports must rebind any deleted column names (`valnominalbrl` → `val_nominal_brl`, etc.).

## GCS bucket protections

Versioning and lifecycle rules are now applied idempotently on `ensure_bucket` — existing buckets are upgraded on the next run.

## `val_nominal_*` → `val_yearfx_*`

The 4 BRL/USD/EUR/CNY columns were renamed because "nominal" was misleading (Silver already converts everything to current BRL numerary via the currency reform seed). Looker Studio reports need to rebind the 4 metrics — see `docs/looker_studio_setup.md`.
