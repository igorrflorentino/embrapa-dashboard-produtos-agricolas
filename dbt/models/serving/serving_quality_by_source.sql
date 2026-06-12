{{ config(materialized='table') }}

-- ────────────────────────────────────────────────────────────────────────────
-- serving_quality_by_source — data_quality_flag breakdown per source.
--
-- Backs the dashboard's quality donut (brief §3.5: id, count, share) for every
-- bank from one tiny pre-counted table, so the UI never scans a Gold fact just to
-- tally flags. `share` sums to 1 within each source.
--
-- Grain: one row per (source, data_quality_flag).
-- ────────────────────────────────────────────────────────────────────────────

with flags as (

    select 'ibge_pevs'  as source, data_quality_flag from {{ ref('gold_pevs_production') }}
    union all
    select 'ibge_pam'   as source, data_quality_flag from {{ ref('gold_pam_production') }}
    union all
    select 'mdic_comex' as source, data_quality_flag from {{ ref('gold_comex_flows') }}
    union all
    select 'un_comtrade' as source, data_quality_flag from {{ ref('gold_comtrade_flows') }}

)

select
    source,
    data_quality_flag,
    count(*)                                                          as n_rows,
    safe_divide(count(*), sum(count(*)) over (partition by source))   as share
from flags
group by source, data_quality_flag
