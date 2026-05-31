{{ config(materialized='view') }}

{#-
    Unified FX rates the Gold deflation reads: BCB SGS (USD, EUR — daily PTAX)
    plus externally-sourced currencies the BCB does not publish (CNY, from the
    ECB via silver_extfx_currency). A thin view so the Gold fx CTEs have a single
    `(series_code, currency, reference_date, reference_year, reference_month,
    brl_per_foreign_unit, ingestion_timestamp)` source for every currency.
    Add a new external currency by extending silver_extfx_currency.
-#}

select * from {{ ref('silver_bcb_currency') }}
union all
select * from {{ ref('silver_extfx_currency') }}
