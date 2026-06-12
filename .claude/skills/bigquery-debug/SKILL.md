---
name: bigquery-debug
description: >-
  Debug BigQuery errors, inspect data in Bronze/Silver/Gold, troubleshoot
  schema mismatches, permission issues, or data quality problems. Use when
  there are BigQuery errors, 404/403/400 from BQ, schema questions, or when
  asked to inspect or query tables directly.
---

# BigQuery Debug — Embrapa Commodities

## Dataset Map

| Layer | Prod dataset | Dev dataset | Description |
|-------|-------------|-------------|-------------|
| Bronze IBGE | `bronze_ibge` | `bronze_ibge` | Append-only, all STRING except `ingestion_timestamp` |
| Bronze BCB | `bronze_bcb` | `bronze_bcb` | Append-only, all STRING except `ingestion_timestamp` |
| Silver | `silver` | `dbt_dev_silver` | Typed, deduped, currency-adjusted |
| Gold | `gold` | `dbt_dev_gold` | Denormalized commodity matrix |

## Authentication

```powershell
# Local dev — Application Default Credentials
gcloud auth application-default login

# Cloud Run — uses the service account attached to the Cloud Run revision
# SA needs: bigquery.dataViewer, bigquery.jobUser, bigquery.readSessionUser
```

## Validate & Estimate Cost (dry-run)

Before running any ad-hoc or generated query, validate syntax and check estimated bytes:

```powershell
bq query --dry_run --use_legacy_sql=false '
  SELECT reference_year, SUM(val_real_ipca_brl) AS total
  FROM `<project>.gold.gold_pevs_production`
  GROUP BY 1
'
# Output: "Query successfully validated. Estimated 12345678 bytes processed."
```

This costs nothing and catches syntax errors, missing columns, and table-not-found before burning quota. **Always dry-run generated SQL that touches large Bronze tables.**

## Diagnostic Queries

### Last ingestion per Bronze table
```sql
SELECT MAX(ingestion_timestamp) AS last_ingestion
FROM `<project>.bronze_ibge.sidra_t289_raw`;

SELECT MAX(ingestion_timestamp) AS last_ingestion
FROM `<project>.bronze_bcb.inflation_series_raw`;

SELECT MAX(ingestion_timestamp) AS last_ingestion
FROM `<project>.bronze_bcb.currency_series_raw`;
```

### Gold table overview
```sql
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT reference_year) AS years,
  COUNT(DISTINCT state_acronym) AS states,
  COUNT(DISTINCT product_code) AS products,
  MIN(reference_year) AS year_min,
  MAX(reference_year) AS year_max,
  MAX(last_refresh) AS last_refresh
FROM `<project>.gold.gold_pevs_production`;
```

### Data quality flags
```sql
SELECT
  data_quality_flag,
  COUNT(*) AS n,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct
FROM `<project>.gold.gold_pevs_production`
GROUP BY 1
ORDER BY 2 DESC;
```

### Check for duplicate natural keys in Bronze
```sql
SELECT ano, municipio_codigo, tipo_de_produto_extrativo_codigo, variavel_codigo,
       COUNT(*) AS dupes
FROM `<project>.bronze_ibge.sidra_t289_raw`
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
ORDER BY dupes DESC
LIMIT 20;
```

### Check Silver dedup correctness
```sql
SELECT reference_year, city_code, product_code, variable_code,
       COUNT(*) AS n
FROM `<project>.silver.silver_ibge_pevs`
GROUP BY 1, 2, 3, 4
HAVING n > 1;
-- Should return 0 rows.
```

### Verify IPCA chain index
```sql
SELECT series_code, reference_date, percent_change, chain_index
FROM `<project>.silver.silver_bcb_inflation`
WHERE series_code = '433'
ORDER BY reference_date DESC
LIMIT 20;
```

## Common Errors

### `404 — Dataset/Table not found`

**Cause:** `BQ_GOLD_DATASET` or `BQ_LOCATION` in `.env` doesn't match the actual BigQuery configuration.

**Fix:**
```powershell
# Check what datasets exist
bq ls --project_id=<project>
# Check dataset location
bq show --format=prettyjson <project>:gold | Select-String "location"
```
Ensure `BQ_LOCATION` in `.env` matches the actual dataset location.

### `403 — Permission denied`

**Cause:** The service account or ADC user lacks necessary IAM roles.

**Required roles:**
- `roles/bigquery.dataViewer` — read data
- `roles/bigquery.jobUser` — run queries
- `roles/bigquery.readSessionUser` — for BigQuery Storage API (used by dashboard for fast reads)

**Docs:** See `docs/iam_setup.md` for the full IAM configuration.

### `400 — Bad Request`

**Cause:** Usually a schema mismatch between what the code expects and what dbt produced. Most common after renaming or adding columns.

**Fix:** Check the Gold table schema:
```powershell
bq show --format=prettyjson <project>:gold.gold_pevs_production | Select-String "fields" -Context 0,50
```
Compare with the expected columns in `gold_pevs_production.sql`.

### Slow queries / high costs

**Bronze tables are partitioned by** `DATE(ingestion_timestamp)` and clustered:
- IBGE: `municipio_codigo, ano, variavel_codigo`
- BCB: `series_code, reference_date_str`

Always filter by partition column in ad-hoc queries to avoid full scans.

## Table Schemas (key columns)

### `gold.gold_pevs_production` (28 columns)
```
reference_year, reference_date,
state_acronym, state_name, region,
city_code, city_name,
product_code, product_description,
family, unit_native, qty_native, qty_base, base_unit,   -- physical-unit family (NEVER SUM qty_base across families — GROUP BY family)
val_yearfx_brl, val_yearfx_usd, val_yearfx_eur,
val_real_ipca_brl,  val_real_ipca_usd,  val_real_ipca_eur,
val_real_igpm_brl,  val_real_igpm_usd,  val_real_igpm_eur,
val_real_igpdi_brl, val_real_igpdi_usd, val_real_igpdi_eur,
data_quality_flag, last_refresh
```
