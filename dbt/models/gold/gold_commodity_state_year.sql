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

-- State-year pre-aggregate. Drops municipal granularity in exchange for ~10×
-- fewer rows (~3k vs ~30k+) — meant for executive Looker pages that only
-- filter by state/region/year/product. Drill-down pages stay on the wide
-- gold_commodity_matrix.

select
    reference_year,
    reference_date,
    state_acronym,
    state_name,
    region,
    product_code,
    any_value(product_description) as product_description,

    -- ── Quantities (sums across municipalities) ───────────────────────────
    sum(quantity_kg)       as quantity_kg,
    sum(quantity_tons)     as quantity_tons,
    sum(quantity_m3)       as quantity_m3,
    sum(quantity_liters)   as quantity_liters,

    -- ── Nominal (foreign columns SUM to NULL pre-1994 because each row is NULL) ──
    sum(val_nominal_brl)   as val_nominal_brl,
    sum(val_nominal_usd)   as val_nominal_usd,
    sum(val_nominal_eur)   as val_nominal_eur,
    sum(val_nominal_cny)   as val_nominal_cny,

    -- ── Real via IPCA ─────────────────────────────────────────────────────
    sum(val_real_ipca_brl) as val_real_ipca_brl,
    sum(val_real_ipca_usd) as val_real_ipca_usd,
    sum(val_real_ipca_eur) as val_real_ipca_eur,
    sum(val_real_ipca_cny) as val_real_ipca_cny,

    -- ── Real via IGP-M ────────────────────────────────────────────────────
    sum(val_real_igpm_brl) as val_real_igpm_brl,
    sum(val_real_igpm_usd) as val_real_igpm_usd,
    sum(val_real_igpm_eur) as val_real_igpm_eur,
    sum(val_real_igpm_cny) as val_real_igpm_cny,

    -- ── Coverage + provenance ─────────────────────────────────────────────
    count(*)                                 as n_municipalities_total,
    countif(data_quality_flag = 'OK')        as n_municipalities_ok,
    max(last_refresh)                        as last_refresh

from {{ ref('gold_commodity_matrix') }}
group by reference_year, reference_date, state_acronym, state_name, region, product_code
