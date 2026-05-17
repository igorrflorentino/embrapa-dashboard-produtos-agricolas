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
-- This index captures pure REAL inflation only — it does NOT absorb the
-- Brazilian currency reforms (Cz$→NCz$→Cr$→CR$→R$) because those reforms
-- divided the currency without changing purchasing power, so the SGS 433
-- monthly variation series shows no spike at reform dates. Nominal historical
-- values therefore must be converted to BRL via the
-- `historical_currency_factors` seed BEFORE this index is applied for
-- inflation correction in Gold.
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
