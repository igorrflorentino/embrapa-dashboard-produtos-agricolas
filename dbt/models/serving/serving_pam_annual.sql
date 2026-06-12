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
-- serving_pam_annual — pre-aggregated IBGE PAM mart for Pushdown Computing.
--
-- COLUMN-IDENTICAL to serving_pevs_annual (plus area_* extras) so the generic,
-- source-parameterized gateway readers (fetch_products / fetch_product_timeseries
-- / fetch_production_overview / fetch_production_by_uf) serve PAM with no
-- per-source SQL — PAM rides the entire PEVS-shaped snapshot and the
-- currency/correction toggles for free.
--
-- Rolls gold_pam_production (year × UF × CITY × product) up to
-- (year × UF × product × family), dropping the municipality grain. Area columns
-- are summed (additive across cities); yield is intentionally NOT carried (a
-- ratio is not summable — recompute as qty/area in the future área/rendimento
-- expansion). Grain: one row per (reference_year, state_acronym, product_code, family).
-- ────────────────────────────────────────────────────────────────────────────

with pam as (

    select
        reference_year,
        state_acronym,
        product_code,
        family,
        any_value(product_description)  as product_description,
        any_value(base_unit)            as base_unit,
        any_value(unit_native)          as unit_native,
        -- qty_native / qty_base summed WITHIN a family (family is in the grain) —
        -- never the forbidden cross-family sum. Monetary values are family-agnostic.
        sum(qty_native)                 as qty_native,
        sum(qty_base)                   as qty_base,
        sum(area_planted_ha)            as area_planted_ha,
        sum(area_harvested_ha)          as area_harvested_ha,
        sum(val_yearfx_brl)             as val_yearfx_brl,
        sum(val_yearfx_usd)             as val_yearfx_usd,
        -- EUR carried alongside BRL/USD (real BCB BRL/EUR series). CNY is
        -- intentionally excluded: gold val_*_cny are all NULL (no BCB BRL/CNY
        -- series), so the mart must not offer a currency it can't honestly serve.
        sum(val_yearfx_eur)             as val_yearfx_eur,
        sum(val_real_ipca_brl)          as val_real_ipca_brl,
        sum(val_real_ipca_usd)          as val_real_ipca_usd,
        sum(val_real_ipca_eur)          as val_real_ipca_eur,
        sum(val_real_igpm_brl)          as val_real_igpm_brl,
        sum(val_real_igpm_eur)          as val_real_igpm_eur,
        sum(val_real_igpdi_brl)         as val_real_igpdi_brl,
        sum(val_real_igpdi_eur)         as val_real_igpdi_eur,
        count(distinct city_name)       as n_cities,
        count(*)                        as source_rows,
        max(last_refresh)               as last_refresh
    from {{ ref('gold_pam_production') }}
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
    p.area_planted_ha,
    p.area_harvested_ha,
    p.val_yearfx_brl,
    p.val_yearfx_usd,
    p.val_yearfx_eur,
    p.val_real_ipca_brl,
    p.val_real_ipca_usd,
    p.val_real_ipca_eur,
    p.val_real_igpm_brl,
    p.val_real_igpm_eur,
    p.val_real_igpdi_brl,
    p.val_real_igpdi_eur,
    p.n_cities,
    p.source_rows,
    p.last_refresh
from pam p
left join {{ ref('dim_geo_br') }} g
    on g.state_acronym = p.state_acronym
-- source='pam' has no crosswalk rows yet → commodity_id/name come out NULL
-- (the dashboard handles NULL commodity); it lights up if 'pam' rows are seeded.
left join {{ ref('gold_commodity_crosswalk') }} x
    on x.source = 'pam' and x.code = p.product_code
