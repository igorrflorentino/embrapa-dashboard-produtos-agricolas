---
name: dbt-workflow
description: >-
  Run, create, modify, test, or debug dbt models (Silver/Gold), seeds, macros,
  and tests. Use when asked to work with dbt, create a new model, fix dbt test
  failures, add columns to Silver/Gold, modify the medallion pipeline
  transforms, or understand the schema separation.
---

# dbt Workflow — Embrapa Commodities

## Quick Commands

```powershell
# Dev (sandboxed in dbt_dev_silver / dbt_dev_gold):
make dbt-build               # build all models
cd dbt && uv run dbt run --select silver_ibge_pevs+   # single model + downstream
cd dbt && uv run dbt test --select gold_commodity_matrix

# Prod (writes to silver / gold — only after dev validation):
make dbt-build-prod           # full-refresh against real datasets

# Test:
make dbt-test
cd dbt && uv run dbt test
```

## Dev/Prod Schema Separation

The macro `dbt/macros/generate_schema_name.sql` enforces:

| Target | Schema result | Example |
|--------|---------------|---------|
| `dev` (default) | `<target.schema>_<custom_schema>` | `dbt_dev_silver`, `dbt_dev_gold` |
| `prod` | `<custom_schema>` only | `silver`, `gold` |

**Always iterate on `make dbt-build` (dev).** `make dbt-build-prod` does `--full-refresh` against real datasets — only run after dev validation.

**Dev schemas auto-expire after 7 days** via the `apply_dev_ttl` macro (`on-run-end` hook in `dbt_project.yml`).

## Model Patterns

### Silver — `dbt/models/silver/`

- **Materialization:** `table` (default). Exception: `silver_ibge_pevs` is `incremental` with `insert_overwrite` partitioned by `reference_year`.
- **Dedup pattern** (Bronze is append-only):
  ```sql
  select *
  from {{ source('bronze_ibge', 'sidra_raw') }}
  qualify row_number() over (
      partition by <natural_key_columns>
      order by ingestion_timestamp desc
  ) = 1
  ```
- **Incremental strategy** (silver_ibge_pevs): scan only partitions with new Bronze rows since last Silver build, then `insert_overwrite` the affected `reference_year` partitions. Use `--full-refresh` after schema changes.
- **Naming:** `silver_<source>_<entity>` (e.g. `silver_bcb_inflation`, `silver_ibge_pevs`).

### Gold — `dbt/models/gold/`

- **Materialization:** `table` (current). The main model is `gold_commodity_matrix`.
- **Columns:** 22 columns per `(reference_year, state_acronym, city_name, product_code)`.
- **Monetary conventions:**
  - `val_yearfx_*` — raw value ÷ year's average FX. NULL pre-1994.
  - `val_real_{ipca,igpm}_*` — value projected to today via chain-linked IPCA/IGP-M index. **Use this for cross-year comparison.**
- **Naming:** `gold_<entity>` (e.g. `gold_commodity_matrix`, `gold_commodity_state_year`).

### Seeds — `dbt/seeds/`

- Land in the same dataset as Silver.
- Key seed: `historical_currency_factors` — date-aware multiplier that absorbs the "Mil" multiplier AND cumulative Brazilian currency reforms. **Without this factor, pre-1994 values are 10⁶–10⁹× too large.**
- Seed join is date-aware: `(unit_of_measure, reference_year BETWEEN year_from AND year_to)`.

### Macros — `dbt/macros/`

| Macro | Purpose |
|-------|---------|
| `generate_schema_name` | Dev/prod schema routing |
| `apply_dev_ttl` | Auto-expire dev tables after N days |
| `safe_numeric` | Parse string to numeric, handling nulls |
| `data_quality_flag` | Classify row quality (OK / MISSING_VALUE / MISSING_QUANTITY / INCOMPLETE) |
| `state_dimensions` | State acronym → name + region mapping |

## Adding / Modifying Models — Checklist

1. Create/edit `.sql` file in `dbt/models/silver/` or `dbt/models/gold/`.
2. Add schema tests in `_silver.yml` or `_gold.yml` (same directory).
3. Run `make dbt-build` to test in dev.
4. Run `make dbt-test` to validate schema tests pass.
5. If incremental model, test with `--full-refresh` too.
6. Only then `make dbt-build-prod`.

## dbt Variables (from `dbt_project.yml`)

```yaml
vars:
  ibge_variable_quantity: "144"
  ibge_variable_value: "145"
  inflation_series_ipca: "{{ env_var('BCB_INFLATION_SERIES_IPCA_CODE', '433') }}"
  inflation_series_igpm: "{{ env_var('BCB_INFLATION_SERIES_IGPM_CODE', '189') }}"
```

If you change BCB series codes in `.env`, also update these vars.

## Gotchas

- `silver_bcb_*` remain `materialized=table` (small tables; the IPCA chain index requires a full-series window scan).
- The IPCA chain in `silver_bcb_inflation.sql` uses `100 * exp(sum(log(1 + pct/100)) over (...))` — this is a log-additive compound, not a simple product.
- Adding a new historical-currency unit string: add a row to `dbt/seeds/historical_currency_factors.csv` with a non-overlapping `[year_from, year_to]` range.
