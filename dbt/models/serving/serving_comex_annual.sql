{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['flow', 'ncm_code', 'country_code']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- serving_comex_annual — pre-aggregated COMEX mart (annual; month + transport
-- route collapsed).
--
-- gold_comex_flows is monthly and carries `transport_route_code` (via) in its
-- grain — a heavy multiplier the dashboard's annual/partner/UF views never need.
-- This mart sums over month and via down to
-- (year × flow × NCM × UF × country). Seasonality (which DOES need the month)
-- is served separately by serving_comex_seasonality.
--
-- Backs: overviewTS / productTS (annual rollup), ufData (by state_acronym),
-- partnerData & flowData (by country_code, flow), products (distinct ncm_code +
-- unit/family). Carries the same family/unit/qty set as serving_pevs_annual so
-- the BFF reads products/productTS uniformly across sources. Raw US$ / kg /
-- native-unit magnitudes — the BFF scales to display units per the data contract.
--
-- Grain: one row per
-- (reference_year, flow, ncm_code, state_acronym, country_code, family).
-- ────────────────────────────────────────────────────────────────────────────

with comex as (

    select
        reference_year,
        flow,
        ncm_code,
        state_acronym,
        country_code,
        -- family in the grain (like serving_pevs_annual) keeps qty_base summable
        -- WITHIN a family; an NCM maps to one family in the common case, so this
        -- adds no rows there and correctly splits the rare mixed-unit NCM.
        family,
        any_value(hs_chapter)       as hs_chapter,
        any_value(ncm_description)  as ncm_description,
        any_value(country_name)     as country_name,
        any_value(country_iso_a3)   as country_iso_a3,
        any_value(unit_native)      as unit_native,
        any_value(base_unit)        as base_unit,
        sum(qty_native)             as qty_native,
        sum(qty_base)               as qty_base,
        sum(val_yearfx_usd)         as val_yearfx_usd,
        sum(val_real_ipca_usd)      as val_real_ipca_usd,
        sum(net_weight_kg)          as net_weight_kg,
        sum(val_freight_usd)        as val_freight_usd,
        sum(val_insurance_usd)      as val_insurance_usd,
        count(*)                    as source_rows,
        max(last_refresh)           as last_refresh
    from {{ ref('gold_comex_flows') }}
    group by reference_year, flow, ncm_code, state_acronym, country_code, family

)

select
    c.reference_year,
    date(c.reference_year, 12, 31)  as reference_date,
    c.flow,
    c.ncm_code,
    c.hs_chapter,
    c.ncm_description,
    c.state_acronym,
    g.state_name,
    g.region,
    g.region_abbrev,
    c.country_code,
    c.country_name,
    c.country_iso_a3,
    x.commodity_id,
    x.commodity_name,
    c.family,
    c.unit_native,
    c.base_unit,
    c.qty_native,
    c.qty_base,
    c.val_yearfx_usd,
    c.val_real_ipca_usd,
    c.net_weight_kg,
    c.val_freight_usd,
    c.val_insurance_usd,
    c.source_rows,
    c.last_refresh
from comex c
left join {{ ref('dim_geo_br') }} g
    on g.state_acronym = c.state_acronym
left join {{ ref('gold_commodity_crosswalk') }} x
    on x.source = 'comex' and x.code = c.ncm_code
