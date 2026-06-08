{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['flow', 'cmd_code', 'reporter_code']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- serving_comtrade_annual — pre-aggregated COMTRADE mart (global bilateral).
--
-- gold_comtrade_flows is already at (year × flow × reporter × partner × cmd), so
-- here the win is COLUMN pruning + clustering + crosswalk conformance rather than
-- row reduction: the dashboard reads a narrow, clustered table (the handful of
-- columns the partner/flow/market-share views use) instead of the wide Gold fact.
-- The `world_exp` denominator (brief §5) is derived by summing over reporters at
-- query time — the World partner is already dropped in Silver, so SUM is clean.
--
-- Grain: one row per (reference_year, flow, cmd_code, reporter_code, partner_code).
-- ────────────────────────────────────────────────────────────────────────────

with comtrade as (

    select
        reference_year,
        flow,
        cmd_code,
        reporter_code,
        partner_code,
        any_value(hs_chapter)       as hs_chapter,
        any_value(cmd_description)  as cmd_description,
        any_value(reporter_name)    as reporter_name,
        any_value(reporter_iso_a3)  as reporter_iso_a3,
        any_value(partner_name)     as partner_name,
        any_value(partner_iso_a3)   as partner_iso_a3,
        sum(val_yearfx_usd)         as val_yearfx_usd,
        sum(val_real_ipca_usd)      as val_real_ipca_usd,
        sum(net_weight_kg)          as net_weight_kg,
        count(*)                    as source_rows,
        max(last_refresh)           as last_refresh
    from {{ ref('gold_comtrade_flows') }}
    group by reference_year, flow, cmd_code, reporter_code, partner_code

)

select
    ct.reference_year,
    date(ct.reference_year, 12, 31) as reference_date,
    ct.flow,
    ct.cmd_code,
    ct.hs_chapter,
    ct.cmd_description,
    ct.reporter_code,
    ct.reporter_name,
    ct.reporter_iso_a3,
    ct.partner_code,
    ct.partner_name,
    ct.partner_iso_a3,
    x.commodity_id,
    x.commodity_name,
    ct.val_yearfx_usd,
    ct.val_real_ipca_usd,
    ct.net_weight_kg,
    ct.source_rows,
    ct.last_refresh
from comtrade ct
left join {{ ref('gold_commodity_crosswalk') }} x
    on x.source = 'comtrade' and x.code = ct.cmd_code
