{{ config(materialized='view') }}

{#-
    Unified FX rates the Gold deflation reads: BCB SGS (USD, EUR — daily PTAX).
    A thin view so the Gold fx CTEs have a single `(series_code, currency,
    reference_date, reference_year, reference_month, brl_per_foreign_unit,
    ingestion_timestamp)` source for every currency.
-#}

select * from {{ ref('silver_bcb_currency') }}
