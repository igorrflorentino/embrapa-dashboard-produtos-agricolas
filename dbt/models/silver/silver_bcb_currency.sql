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

)

select
    series_code,
    currency,
    safe.parse_date('%d/%m/%Y', reference_date_str)                       as reference_date,
    extract(year  from safe.parse_date('%d/%m/%Y', reference_date_str))   as reference_year,
    extract(month from safe.parse_date('%d/%m/%Y', reference_date_str))   as reference_month,
    {{ safe_numeric('value_str') }}                                       as brl_per_foreign_unit,
    ingestion_timestamp
from deduplicated
where safe.parse_date('%d/%m/%Y', reference_date_str) is not null
