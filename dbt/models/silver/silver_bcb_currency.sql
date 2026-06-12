{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['currency']
    )
}}

{#-
    Stays materialized=table (not incremental) for symmetry with
    silver_bcb_inflation. The table is small (USD + EUR daily PTAX) so the
    rebuild cost is negligible — the real win against API/Bronze growth comes
    from BCB delta-ingest (see bcb pipelines).

    Surfaces ONLY the BCB SGS series the ingestion config currently pulls —
    USD (1) + EUR (21619) as daily PTAX — by filtering series_code to the
    `currency_series` var (mirrors BCB_CURRENCY_SERIES / config.py).

    The series_code filter matters because Bronze is APPEND-ONLY: a series from a
    past config can still sit in Bronze long after being dropped from the series
    list. Without the filter those stale rows would leak into silver_currency.
    Keep in sync with config.py's bcb_currency_series.
-#}

{#- Valid BCB FX series codes from config, e.g. "1:USD,21619:EUR" -> '1', '21619'. -#}
{%- set _currency_codes = [] -%}
{%- for _pair in var('currency_series', '1:USD,21619:EUR').split(',') if _pair.strip() -%}
    {%- do _currency_codes.append("'" ~ _pair.split(':')[0].strip() ~ "'") -%}
{%- endfor -%}

with deduplicated as (

    select *
    from {{ source('bronze_bcb', 'currency_raw') }}
    where series_code in ({{ _currency_codes | join(', ') }})
    qualify row_number() over (
        partition by series_code, reference_date_str
        order by ingestion_timestamp desc
    ) = 1

),

parsed as (

    select
        series_code,
        currency,
        safe.parse_date('%d/%m/%Y', reference_date_str)  as reference_date,
        {{ safe_numeric('value_str') }}                  as brl_per_foreign_unit,
        ingestion_timestamp
    from deduplicated

)

select
    series_code,
    currency,
    reference_date,
    extract(year  from reference_date) as reference_year,
    extract(month from reference_date) as reference_month,
    brl_per_foreign_unit,
    ingestion_timestamp
from parsed
where reference_date is not null
