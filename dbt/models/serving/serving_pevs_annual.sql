{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['state_acronym', 'product_code']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- serving_pevs_annual — pre-aggregated PEVS mart for Pushdown Computing.
--
-- Rolls gold_pevs_production (year × UF × CITY × product) up to
-- (year × UF × product × family), dropping the municipality grain — the row
-- multiplier the dashboard never charts directly. This is the GB→MB reduction
-- that lets the stateless Dash app push a parameterized GROUP BY down to BigQuery
-- and scan a small, clustered table instead of the full Gold fact.
--
-- Backs (frontend_data_contract.md §3): overviewTS (GROUP BY year), productTS
-- (GROUP BY year, product_code), ufData (GROUP BY state_acronym). Carries
-- commodity_id so the UI can LEFT JOIN dim_commodity_scd2 live at query time.
--
-- Grain: one row per (reference_year, state_acronym, product_code, family).
-- ────────────────────────────────────────────────────────────────────────────

with pevs as (

    select
        reference_year,
        state_acronym,
        product_code,
        family,
        any_value(product_description)  as product_description,
        any_value(base_unit)            as base_unit,
        any_value(unit_native)          as unit_native,
        -- qty_native / qty_base are summed WITHIN a family (family is in the grain),
        -- so this is never the forbidden cross-family sum. Monetary values are
        -- family-agnostic. qty_native stays in unit_native — the quantity productTS
        -- charts (frontend_data_contract.md §3.3); qty_base is the normalised one.
        sum(qty_native)                 as qty_native,
        sum(qty_base)                   as qty_base,
        sum(val_yearfx_brl)             as val_yearfx_brl,
        sum(val_yearfx_usd)             as val_yearfx_usd,
        sum(val_real_ipca_brl)          as val_real_ipca_brl,
        sum(val_real_ipca_usd)          as val_real_ipca_usd,
        sum(val_real_igpm_brl)          as val_real_igpm_brl,
        sum(val_real_igpdi_brl)         as val_real_igpdi_brl,
        count(distinct city_name)       as n_cities,
        count(*)                        as source_rows,
        max(last_refresh)               as last_refresh
    from {{ ref('gold_pevs_production') }}
    group by reference_year, state_acronym, product_code, family

)

select
    p.reference_year,
    date(p.reference_year, 12, 31)  as reference_date,
    p.state_acronym,
    g.state_name,
    g.region,
    g.region_abbrev,
    x.commodity_id,
    x.commodity_name,
    p.product_code,
    p.product_description,
    p.family,
    p.base_unit,
    p.unit_native,
    p.qty_native,
    p.qty_base,
    p.val_yearfx_brl,
    p.val_yearfx_usd,
    p.val_real_ipca_brl,
    p.val_real_ipca_usd,
    p.val_real_igpm_brl,
    p.val_real_igpdi_brl,
    p.n_cities,
    p.source_rows,
    p.last_refresh
from pevs p
left join {{ ref('dim_geo_br') }} g
    on g.state_acronym = p.state_acronym
left join {{ ref('gold_commodity_crosswalk') }} x
    on x.source = 'pevs' and x.code = p.product_code
