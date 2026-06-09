# Looker Studio — Dashboard Setup

## Prerequisite: run `make dbt-build-prod`

Looker Studio must point to the **production** datasets (`silver`, `gold`),
not the dev ones (`dbt_dev_silver`, `dbt_dev_gold`). Make sure you have run:

```bash
make dbt-build-prod
```

This creates `embrapa-dashboard-commodities.gold.gold_pevs_production` with the complete data.

---

## 1. Enable BI Engine (optional)

BI Engine is a caching technology that speeds up BigQuery queries.

Looker Studio provides 1Gb of BI Engine for free. It will not be necessary for this project, but it may be useful for future use cases.

It improves dashboard performance, especially if you have complex queries or large data volumes. It can also help reduce costs, since queries that use BI Engine are not billed by bytes scanned.

1. Go to: **BigQuery → BI Engine → Reservations** in the GCP console
2. Click **Create Reservation**
3. Settings:
   - **Project**: `embrapa-dashboard-commodities`
   - **Location**: `us-central1` (same as your BQ_LOCATION)
   - **Capacity**: `[set the capacity, e.g.: 1Gb]`
4. Click **Create**

Estimated cost: ~US$ 30/month/Gb.

> Before enabling BI Engine, configure the budget and quota in
> [cost_safety.md](cost_safety.md) — that way any unexpected cost triggers
> an automatic alert.

---

## 2. Create the report in Looker Studio

### 2a. Access Looker Studio

1. Go to [lookerstudio.google.com](https://lookerstudio.google.com)
2. Click **+ Create → Report**

### 2b. Connect to the Gold table

There is **a single physical Gold table per source** — for IBGE PEVS it is
`gold_pevs_production` (~95 thousand rows, one per year × UF × municipality × product).
Aggregations by state/year or Brazil-total are derived within Looker
Studio itself (calculated fields / GROUP BY on the source). Pre-aggregated marts exist in the
`serving/` layer (for the Dash dashboard / Pushdown Computing), but Looker
consumes Gold directly.

| Table | Rows (approx.) | Grain |
|---|---|---|
| `gold_pevs_production` | ~95 thousand | year × UF × municipality × product (full drill-down) |

Connect:

1. Under "Add data to report", select **BigQuery**
2. Sign in with the account that has access to the project
3. Navigate: **My projects → embrapa-dashboard-commodities → gold → gold_pevs_production**
4. Click **Add** → **Add to report**

> **Important:** connect directly to the table, not via "Custom Query".
> BI Engine only accelerates direct connections to the physical table.

### 2c. Configure default fields

On the data source configuration screen, adjust:

| Field | Suggested type | Default aggregation |
|---|---|---|
| `reference_year` | Number (year) | — |
| `reference_date` | Date (YYYY-MM-DD) | — |
| `state_acronym` | Text | — |
| `state_name` | Text | — |
| `region` | Text | — |
| `city_code` | Text / Geo → "Brazilian Municipality" | — |
| `city_name` | Text | — |
| `product_code` | Text | — |
| `product_description` | Text | — |
| `family` | Text | — (always use as a quantity dimension/filter) |
| `unit_native` | Text | — |
| `base_unit` | Text | — |
| `qty_native` | Number | Sum (**only when filtering by a single `family`/`unit_native`**) |
| `qty_base` | Number | Sum (**only with `family` in the breakdown — never across families**) |
| `val_yearfx_brl` | Number (BRL currency) | Sum |
| `val_yearfx_usd` | Number (USD currency) | Sum |
| `val_yearfx_eur` | Number (EUR currency) | Sum |
| `val_yearfx_cny` | Number (CNY currency) | Sum |
| `val_real_ipca_brl` | Number (BRL currency) | Sum |
| `val_real_ipca_usd` | Number (USD currency) | Sum |
| `val_real_ipca_eur` | Number (EUR currency) | Sum |
| `val_real_ipca_cny` | Number (CNY currency) | Sum |
| `val_real_igpm_brl` | Number (BRL currency) | Sum |
| `val_real_igpm_usd` | Number (USD currency) | Sum |
| `val_real_igpm_eur` | Number (EUR currency) | Sum |
| `val_real_igpm_cny` | Number (CNY currency) | Sum |
| `data_quality_flag` | Text | — |
| `last_refresh` | Date and time | Maximum |

---

## 3. Recommended default filter

Add a **report filter** for exploratory analyses:

- Field: `data_quality_flag`
- Condition: **Equal to** `OK`

This excludes rows where IBGE did not publish a monetary value (e.g.: Pinheiro brasileiro).

---

## 4. Suggested page structure

### Page 1 — Overview

| Chart | Configuration |
|---|---|
| Scorecard — Total Real Value IPCA (BRL) | `val_real_ipca_brl` Sum |
| Scorecard — Total Mass (t) | `qty_base` Sum · **filter `family = massa`** |
| Scorecard — Total Volume (m³) | `qty_base` Sum · **filter `family = volume`** |
| Line chart — Historical series | Dimension: `reference_year` · Metric: `val_real_ipca_brl` |
| Bar chart — By product | Dimension: `product_description` · Metric: `val_real_ipca_brl` |
| Filter — Year | Slider control on `reference_year` |
| Filter — State | Selector on `state_acronym` |
| Filter — Product | Selector on `product_description` |

### Page 2 — Geographic analysis

| Chart | Configuration |
|---|---|
| Choropleth map (Brazil) | Geo: `state_acronym` · Color: `val_real_ipca_brl` |
| Detailed table — Top municipalities | Dimensions: `city_name`, `state_acronym`, `family` · Metrics: `qty_base`, `val_yearfx_brl`, `val_real_ipca_brl` |

### Page 3 — Comparative monetary analysis

| Chart | Configuration |
|---|---|
| Line chart — Nominal vs real values | Series 1: `val_yearfx_brl` · Series 2: `val_real_ipca_brl` · Series 3: `val_real_igpm_brl` |
| Bar chart — By currency | Metrics: `val_real_ipca_usd`, `val_real_ipca_eur`, `val_real_ipca_cny` |

---

## 5. Automatic data refresh

The dashboard reflects the Gold table at query time. To refresh:

```bash
# Incremental ingestion (only new data)
uv run embrapa ingest all

# Rebuild transformations
make dbt-build-prod
```

Set up a cron or GitHub Actions to run this annually (PEVS is published 1× per year).

---

## 6. Transfer to the company

When moving the project to the company:
1. Transfer the report: **Share → Transfer ownership** in Looker Studio.
2. Update the data source to point to the new `GCP_PROJECT_ID`.
3. There is no hardcoded project in the report — only the data source needs to be updated.
