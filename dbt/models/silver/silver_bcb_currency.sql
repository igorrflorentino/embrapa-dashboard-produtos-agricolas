{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['currency']
    )
}}

with deduplicated as (

    select *
    from {{ source('bronze_bcb', 'currency_raw') }}
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
