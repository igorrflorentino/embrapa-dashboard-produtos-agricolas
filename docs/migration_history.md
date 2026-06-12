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

## Gold table rename: `gold_commodity_matrix` → `gold_pevs_production` (2026-05-29)

Adopted the `gold_<source>_<form>` naming convention. The single PEVS Gold table
was renamed from `gold_commodity_matrix` to `gold_pevs_production` (`production` =
output-measurement grain). The dbt model file, `_gold.yml`, and the
`assert_gold_has_rows` test were updated; `dbt build` recreates the table under
the new name automatically.

Two manual cleanups outside this repo (dbt does NOT do these for you):

1. **Looker Studio** — repoint the report's data source from
   `gold.gold_commodity_matrix` to `gold.gold_pevs_production`. Column names are
   unchanged, so metric/dimension bindings survive once the table is rebound.

2. **Orphaned prod table** — after the next `make dbt-build-prod`, the new
   `gold.gold_pevs_production` exists but the old `gold.gold_commodity_matrix`
   lingers (dbt only manages models it knows about; a renamed model leaves the
   old physical table behind). Drop it once the new table is verified:

   ```bash
   bq rm -f -t "${GCP_PROJECT_ID}:gold.gold_commodity_matrix"
   ```

   Do this only AFTER confirming `gold_pevs_production` built and Looker is
   repointed — the drop is irreversible.

## CNY currency removal (2026-06)

The `val_*_cny` columns were dropped from all four Gold facts and the external-FX
seed path (`extfx_cny_brl` → `silver_extfx_currency` → `silver_currency` UNION) was
removed. The Gold tables physically shed the columns only after
`dbt build --full-refresh`; until then the dropped columns linger harmlessly
(nothing reads them). The currency selector now offers BRL/USD/EUR only.
