{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['flow', 'ncm_code']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- serving_comex_seasonality — monthly COMEX mart for the seasonality view.
--
-- The ONLY serving mart that keeps `reference_month` — it backs monthlyData
-- (brief §4.3: matrix[year][1..12], monthlyAvg[12]). Collapses NCM/country/UF/via
-- to (year × month × flow × NCM) and joins dim_date for the localized month label
-- so the chart axis needs no client-side month mapping. COMTRADE is annual and
-- never reaches this mart (Seasonality = "Not applicable").
--
-- Grain: one row per (reference_year, reference_month, flow, ncm_code).
-- ────────────────────────────────────────────────────────────────────────────

with comex as (

    select
        reference_year,
        reference_month,
        flow,
        ncm_code,
        any_value(ncm_description)  as ncm_description,
        sum(val_yearfx_usd)         as val_yearfx_usd,
        sum(net_weight_kg)          as net_weight_kg,
        count(*)                    as source_rows,
        max(last_refresh)           as last_refresh
    from {{ ref('gold_comex_flows') }}
    group by reference_year, reference_month, flow, ncm_code

)

select
    c.reference_year,
    c.reference_month,
    d.month_name_pt,
    d.month_abbr_pt,
    d.quarter,
    c.flow,
    c.ncm_code,
    c.ncm_description,
    c.val_yearfx_usd,
    c.net_weight_kg,
    c.source_rows,
    c.last_refresh
from comex c
left join {{ ref('dim_date') }} d
    on d.date_month = date(c.reference_year, c.reference_month, 1)
