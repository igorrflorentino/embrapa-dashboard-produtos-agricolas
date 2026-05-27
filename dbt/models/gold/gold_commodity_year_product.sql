{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['product_code']
    )
}}

-- National roll-up: one row per (reference_year, product_code). ~10× fewer
-- rows than gold_commodity_state_year, ~1000× fewer than gold_commodity_matrix.
-- Use this for Looker pages that only need "Brasil total by product over time"
-- (line charts, scorecards). Drill-down by state → gold_commodity_state_year.
-- Drill-down by municipality → gold_commodity_matrix.

select
    reference_year,
    reference_date,
    product_code,
    any_value(product_description)   as product_description,

    -- ── Quantities ───────────────────────────────────────────────────────
    sum(quantity_tons)               as quantity_tons,
    sum(quantity_m3)                 as quantity_m3,

    -- ── Year-FX values ───────────────────────────────────────────────────
    sum(val_yearfx_brl)              as val_yearfx_brl,
    sum(val_yearfx_usd)              as val_yearfx_usd,
    sum(val_yearfx_eur)              as val_yearfx_eur,
    sum(val_yearfx_cny)              as val_yearfx_cny,

    -- ── Real via IPCA ────────────────────────────────────────────────────
    sum(val_real_ipca_brl)           as val_real_ipca_brl,
    sum(val_real_ipca_usd)           as val_real_ipca_usd,
    sum(val_real_ipca_eur)           as val_real_ipca_eur,
    sum(val_real_ipca_cny)           as val_real_ipca_cny,

    -- ── Real via IGP-M ───────────────────────────────────────────────────
    sum(val_real_igpm_brl)           as val_real_igpm_brl,
    sum(val_real_igpm_usd)           as val_real_igpm_usd,
    sum(val_real_igpm_eur)           as val_real_igpm_eur,
    sum(val_real_igpm_cny)           as val_real_igpm_cny,

    -- ── Real via IGP-DI ──────────────────────────────────────────────────
    sum(val_real_igpdi_brl)          as val_real_igpdi_brl,
    sum(val_real_igpdi_usd)          as val_real_igpdi_usd,
    sum(val_real_igpdi_eur)          as val_real_igpdi_eur,
    sum(val_real_igpdi_cny)          as val_real_igpdi_cny,

    -- ── Coverage + provenance ────────────────────────────────────────────
    count(*)                                 as n_municipalities_total,
    countif(data_quality_flag = 'OK')        as n_municipalities_ok,
    max(last_refresh)                        as last_refresh

from {{ ref('gold_commodity_matrix') }}
group by reference_year, reference_date, product_code
