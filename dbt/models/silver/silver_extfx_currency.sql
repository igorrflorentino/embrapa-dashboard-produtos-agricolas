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
