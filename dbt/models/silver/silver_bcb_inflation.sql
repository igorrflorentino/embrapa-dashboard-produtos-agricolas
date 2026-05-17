{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['series_code']
    )
}}

with deduplicated as (

    select *
    from {{ source('bronze_bcb', 'inflation_raw') }}
    qualify row_number() over (
        partition by series_code, reference_date_str
        order by ingestion_timestamp desc
    ) = 1

),

parsed as (

    select
        series_code,
        series_name,
        safe.parse_date('%d/%m/%Y', reference_date_str)   as reference_date,
        {{ safe_numeric('value_str') }}                   as monthly_pct_change,
        ingestion_timestamp
    from deduplicated
    where safe.parse_date('%d/%m/%Y', reference_date_str) is not null

)

-- Chain-link the monthly % changes into a 100-base number index.
-- This single column absorbs both inflation AND every Brazilian monetary
-- reform (cuts of zeros, currency renames) because the SGS variation series
-- is constructed by the BCB to be continuous across those events. As a
-- result, a value of 500 Cruzeiros in 1989 multiplied by
-- (index_value_2025 / index_value_1989) yields the correct R$ value in 2025.
select
    series_code,
    series_name,
    reference_date,
    extract(year  from reference_date) as reference_year,
    extract(month from reference_date) as reference_month,
    monthly_pct_change,
    100.0 * exp(
        sum(safe.log(1.0 + monthly_pct_change / 100.0)) over (
            partition by series_code
            order by reference_date
            rows between unbounded preceding and current row
        )
    ) as index_value,
    ingestion_timestamp
from parsed
where monthly_pct_change is not null
