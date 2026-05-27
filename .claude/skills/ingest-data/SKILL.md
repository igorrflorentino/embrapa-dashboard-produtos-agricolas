---
name: ingest-data
description: >-
  Ingest data from external sources (IBGE SIDRA, BCB SGS), add new products or
  series, debug ingestion failures, or understand the Bronze pipeline. Use when
  asked to ingest data, add a new product, add a new BCB series, troubleshoot
  a pipeline failure, or run the data pipeline.
---

# Data Ingestion — Embrapa Commodities

## Quick Commands

```powershell
# Ingest everything (IBGE + BCB inflation + BCB currency)
make ingest-all
uv run embrapa ingest all

# Individual pipelines
uv run embrapa ingest ibge              # IBGE PEVS
uv run embrapa ingest bcb-inflation     # BCB inflation (IPCA, IGP-M)
uv run embrapa ingest bcb-currency      # BCB FX rates (USD, EUR, CNY)

# IBGE large historical windows (auto-chunked)
make ingest-ibge-historical             # uses --chunk-years 5
uv run embrapa ingest ibge-batch --chunk-years 5

# Force full refetch (after schema changes or to backfill)
uv run embrapa ingest bcb-inflation --full
uv run embrapa ingest bcb-currency --full
```

## Architecture

```
IBGE SIDRA API ──┐
BCB SGS API    ──┼──► Python (src/embrapa_commodities/) → GCS Parquet (landing/)
                 ┘                                               │
                                                                 ▼
                                             BigQuery Bronze (WRITE_APPEND)
```

- **Bronze is append-only.** Every Silver model dedupes on the natural key ordered by `ingestion_timestamp desc`.
- All Bronze columns are `STRING` except `ingestion_timestamp`.
- Datasets auto-create on first run (`gcp/bigquery.py` + `gcp/storage.py`).

## BCB Delta Mode (Default)

BCB pipelines are delta by default:
1. Query `max(reference_date_str)` from Bronze.
2. Fetch from BCB starting at `max_date - overlap_window`:
   - **Inflation:** 12 months overlap (absorbs BCB revisions of preliminary readings)
   - **Currency:** 30 days overlap
3. Only write new rows to Bronze.

Use `--full` flag to force a complete refetch from `BCB_START_YEAR`.

## Adding a New IBGE Product

Just update `.env`:
```
IBGE_PRODUCT_CODES=3405,3406,3407,...,<new_code>
```

The product code flows straight through from SIDRA's `tipo_de_produto_extrativo_codigo` — no mapping seed is required.

**Note:** IBGE SIDRA has a per-request cell limit. For windows >10 years, use `ingest ibge-batch`; chunk size auto-scales with number of products (`recommended_chunk_years` in `ibge/client.py`).

## Adding a New BCB Series

1. Update `.env`:
   ```
   BCB_INFLATION_SERIES=433:IPCA,189:IGP-M,...,<CODE>:<LABEL>
   # or for currency:
   BCB_CURRENCY_SERIES=1:USD,21619:EUR,21623:CNY,...,<CODE>:<LABEL>
   ```

2. If the new series is an inflation index used for deflation in Gold:
   - Update `BCB_INFLATION_SERIES_IPCA_CODE`, `BCB_INFLATION_SERIES_IGPM_CODE`, or `BCB_INFLATION_SERIES_IGPDI_CODE` in `.env`
   - These are read by `dbt_project.yml` via `env_var()` and used in Gold's `val_real_*` projections.

## Configuration (`config.py`)

All configuration flows through `src/embrapa_commodities/config.py` (pydantic-settings reading `.env`):

| Key env var | Purpose |
|-------------|---------|
| `GCP_PROJECT_ID` | BigQuery project |
| `GCS_BUCKET` | Landing zone bucket |
| `GCS_LANDING_PREFIX` | Parquet prefix in bucket |
| `IBGE_PRODUCT_CODES` | Comma-separated SIDRA codes |
| `BCB_INFLATION_SERIES` | `CODE:LABEL,CODE:LABEL` |
| `BCB_CURRENCY_SERIES` | `CODE:LABEL,CODE:LABEL` |
| `BCB_START_YEAR` | Earliest year for full-refetch |
| `BQ_BRONZE_IBGE_DATASET` | Bronze IBGE dataset name |
| `BQ_BRONZE_BCB_DATASET` | Bronze BCB dataset name |
| `BQ_LOCATION` | BigQuery dataset location |

## Discovery Helpers

For finding codes and periods before adding new products/series:

```powershell
uv run embrapa discover ibge-periods   --table-id 289
uv run embrapa discover ibge-products  --keywords castanha,madeira
uv run embrapa discover bcb-series     433
```

## Pipeline Structure

```
src/embrapa_commodities/
├── cli.py              # Typer entry point (embrapa ingest ...)
├── config.py           # Pydantic Settings (.env reader)
├── ibge/
│   ├── client.py       # SIDRA API client + auto-chunking
│   └── pipeline.py     # fetch → Parquet → GCS → BigQuery
├── bcb/
│   ├── inflation.py    # BCB SGS inflation pipeline
│   └── currency.py     # BCB SGS currency pipeline
├── gcp/
│   ├── bigquery.py     # BigQuery load + dataset auto-create
│   └── storage.py      # GCS upload + bucket auto-create
└── backup.py           # Gold table cold backup to GCS
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `HTTP 400` from SIDRA | Too many cells in request | Use `ibge-batch --chunk-years 3` |
| `Dataset not found` on ingest | First run, dataset doesn't exist | The code auto-creates — check `GCP_PROJECT_ID` is correct |
| BCB returns empty data | Series code wrong or BCB rate-limiting | Verify with `embrapa discover bcb-series <code>` |
| `Partition mismatch` on load | Table exists without partitioning | Drop the old table first (see CLAUDE.md migration notes) |

## Cold-Storage Backup

After `make dbt-build-prod`, preserve the Gold tables:
```powershell
uv run embrapa backup-gold    # → gs://${GCS_BUCKET}/backups/run=<ts>/...
```
