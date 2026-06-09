{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['currency']
    )
}}

{#-
    External FX rates not published by the BCB — currently just BRL/CNY (the
    yuan is absent from BCB SGS/PTAX). Sourced from the ECB reference rates via
    the `extfx_cny_brl` seed (regenerate with scripts/refresh_cny_seed.py).
    Shaped to match silver_bcb_currency exactly so silver_currency can UNION
    them and the Gold fx CTEs treat every currency uniformly.

    LIMITATION — granularity mismatch: this seed is MONTHLY, whereas USD/EUR
    come from daily PTAX. The Gold `fx_latest` CTE picks each currency's
    most-recent reference_date row, so the "current" CNY rate is the last
    seeded month-end and can lag up to ~a month inside the running month
    (USD/EUR are ~yesterday). The `fx_year`/`fx_month` averages are unaffected
    in practice (a month of dailies vs one monthly point average out closely).
    This is accepted: the dashboard is for historical/scientific time-series
    analysis, not intra-month spot FX. Do NOT re-architect the seed pipeline to
    daily just for CNY recency.
-#}

select
    'frankfurter-cny'                                  as series_code,
    'CNY'                                              as currency,
    reference_date,
    extract(year  from reference_date)                 as reference_year,
    extract(month from reference_date)                 as reference_month,
    brl_per_cny                                        as brl_per_foreign_unit,
    current_timestamp()                                as ingestion_timestamp
from {{ ref('extfx_cny_brl') }}
where reference_date is not null
