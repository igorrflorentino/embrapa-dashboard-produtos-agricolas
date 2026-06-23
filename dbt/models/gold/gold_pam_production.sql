{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['state_acronym', 'product_code', 'city_name']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- gold_pam_production — comprehensive IBGE PAM (crop production) fact.
--
-- Pivots silver_ibge_pam's LONG measure rows into one row per
-- (year × UF × CITY × product) carrying ALL five PAM measures:
--   area_planted_ha / area_harvested_ha (ha) · qty_native (t, the 'massa'
--   quantity) · yield_kg_ha (kg/ha) · val_raw (nominal R$).
-- The monetary measure gets the SAME FX + inflation deflation matrix as
-- gold_pevs_production (val_yearfx_* / val_real_{ipca,igpm,igpdi}_*), so PAM
-- rides the identical currency/correction toggles in the dashboard.
--
-- NOTE: val_raw is nominal R$ for the FULL history — silver_ibge_pam applies the
-- date-aware historical_currency_factors join (same as PEVS), so pre-1994 years
-- (Mil Cruzeiros/Cruzados/…) are reform-corrected. Foreign-FX columns
-- (val_yearfx_{usd,eur}) stay NULL pre-1994 (old-currency PTAX would mix scales);
-- val_real_* (BRL, inflation-deflated) is valid wherever the index covers the year.
-- The dashboard surfaces qty + value + área/rendimento (productivity is live).
-- ────────────────────────────────────────────────────────────────────────────

with base_pam as (

    select
        reference_year,
        state_acronym,
        city_code,
        any_value(city_name)            as city_name,
        product_code,
        any_value(product_description)  as product_description,
        -- One physical unit per product at this grain (Toneladas for the lean
        -- crops) → max() lifts the quantity row's family/unit/qty (NULL on the
        -- non-quantity measure rows). Same single-unit assumption as PEVS.
        max(family)                     as family,
        max(unit_native)                as unit_native,
        max(base_unit)                  as base_unit,
        max(qty_native)                 as qty_native,
        max(qty_base)                   as qty_base,
        -- Pivot the remaining PAM measures by their SIDRA variable code.
        max(case when variable_code = '{{ var("pam_variable_area_planted")   }}' then numeric_value end) as area_planted_ha,
        max(case when variable_code = '{{ var("pam_variable_area_harvested") }}' then numeric_value end) as area_harvested_ha,
        max(case when variable_code = '{{ var("pam_variable_yield")          }}' then numeric_value end) as yield_kg_ha,
        max(case when is_monetary_value then numeric_value end) as val_raw,
        max(ingestion_timestamp)        as last_refresh
    from {{ ref('silver_ibge_pam') }}
    group by reference_year, state_acronym, city_code, product_code
    having qty_native is not null
        or val_raw    is not null
        or area_planted_ha   is not null
        or area_harvested_ha is not null

),

inflation_year_end as (

    select
        reference_year,
        max(case when series_code = '{{ var("inflation_series_ipca")  }}' then index_value end) as ipca_year_end,
        max(case when series_code = '{{ var("inflation_series_igpm")  }}' then index_value end) as igpm_year_end,
        max(case when series_code = '{{ var("inflation_series_igpdi") }}' then index_value end) as igpdi_year_end
    from (
        select reference_year, series_code, index_value
        from {{ ref('silver_bcb_inflation') }}
        where index_value is not null
        qualify row_number() over (
            partition by reference_year, series_code
            order by reference_month desc
        ) = 1
    )
    group by reference_year

),

inflation_latest as (

    select
        max(case when series_code = '{{ var("inflation_series_ipca")  }}' then index_value end) as ipca_current,
        max(case when series_code = '{{ var("inflation_series_igpm")  }}' then index_value end) as igpm_current,
        max(case when series_code = '{{ var("inflation_series_igpdi") }}' then index_value end) as igpdi_current
    from (
        select series_code, index_value
        from {{ ref('silver_bcb_inflation') }}
        where index_value is not null
        qualify row_number() over (
            partition by series_code
            order by reference_date desc
        ) = 1
    )

),

fx_year as (

    select
        reference_year,
        avg(case when currency = 'USD' then brl_per_foreign_unit end) as brl_per_usd_avg,
        avg(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_avg
    from {{ ref('silver_currency') }}
    where brl_per_foreign_unit is not null
        -- 1994 changeover (Plano Real, 1994-07-01): PTAX before that date is
        -- CR$/unit, after it R$/unit. Average only the R$ half for 1994 so
        -- val_yearfx_* stays correct if PAM_START_YEAR is lowered to 1994
        -- (mirrors gold_pevs_production). Pre-1994 years are guarded below.
        and (reference_year != 1994 or reference_date >= date(1994, 7, 1))
    group by reference_year

),

fx_latest as (

    select
        max(case when currency = 'USD' then brl_per_foreign_unit end) as brl_per_usd_current,
        max(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_current
    from (
        select currency, brl_per_foreign_unit
        from {{ ref('silver_currency') }}
        where brl_per_foreign_unit is not null
        qualify row_number() over (
            partition by currency
            order by reference_date desc
        ) = 1
    )

),

enriched as (

    select
        b.*,
        fy.brl_per_usd_avg,
        fy.brl_per_eur_avg,
        fxl.brl_per_usd_current,
        fxl.brl_per_eur_current,

        -- Real BRL via each inflation chain (val_raw already nominal present-era R$).
        b.val_raw * safe_divide(il.ipca_current,  iy.ipca_year_end)  as val_real_ipca_brl,
        b.val_raw * safe_divide(il.igpm_current,  iy.igpm_year_end)  as val_real_igpm_brl,
        b.val_raw * safe_divide(il.igpdi_current, iy.igpdi_year_end) as val_real_igpdi_brl

    from base_pam b
    left join fx_year            fy  on b.reference_year = fy.reference_year
    left join inflation_year_end iy  on b.reference_year = iy.reference_year
    cross join inflation_latest  il
    cross join fx_latest         fxl

)

select
    -- ── Time ─────────────────────────────────────────────────────────────────
    reference_year,
    date(reference_year, 12, 31)                             as reference_date,

    -- ── Geography ────────────────────────────────────────────────────────────
    state_acronym,
    {{ state_name('state_acronym') }}                        as state_name,
    {{ state_region('state_acronym') }}                      as region,
    city_code,
    city_name,

    -- ── Product ──────────────────────────────────────────────────────────────
    product_code,
    product_description,

    -- ── Quantities (physical-unit family — always 'massa'/t for the lean crops) ─
    family,
    unit_native,
    qty_native,
    qty_base,
    base_unit,

    -- ── PAM-specific agronomic measures (carried for the área/rendimento expansion) ─
    area_planted_ha,
    area_harvested_ha,
    yield_kg_ha,

    -- ── Year-FX: val_raw converted via FX of THAT year ──────────────────────
    -- Foreign-FX columns are NULL pre-1994 (old-currency PTAX would mix scales);
    -- 1994 itself is valid — fx_year averages only the R$ half (>= 1994-07-01).
    val_raw                                                  as val_yearfx_brl,
    case when reference_year >= 1994
        then safe_divide(val_raw, brl_per_usd_avg) end       as val_yearfx_usd,
    case when reference_year >= 1994
        then safe_divide(val_raw, brl_per_eur_avg) end       as val_yearfx_eur,

    -- ── Real via IPCA ─────────────────────────────────────────────────────────
    val_real_ipca_brl                                        as val_real_ipca_brl,
    safe_divide(val_real_ipca_brl, brl_per_usd_current)      as val_real_ipca_usd,
    safe_divide(val_real_ipca_brl, brl_per_eur_current)      as val_real_ipca_eur,

    -- ── Real via IGP-M ───────────────────────────────────────────────────────
    val_real_igpm_brl                                        as val_real_igpm_brl,
    safe_divide(val_real_igpm_brl, brl_per_usd_current)      as val_real_igpm_usd,
    safe_divide(val_real_igpm_brl, brl_per_eur_current)      as val_real_igpm_eur,

    -- ── Real via IGP-DI ──────────────────────────────────────────────────────
    val_real_igpdi_brl                                       as val_real_igpdi_brl,
    safe_divide(val_real_igpdi_brl, brl_per_usd_current)     as val_real_igpdi_usd,
    safe_divide(val_real_igpdi_brl, brl_per_eur_current)     as val_real_igpdi_eur,

    -- ── Quality + provenance ─────────────────────────────────────────────────
    -- The flag measures qty+value completeness only. A PAM row admitted by the base
    -- having-clause on AREA alone (area_planted/harvested present, qty_native AND
    -- val_raw both NULL) is therefore correctly 'INCOMPLETE' w.r.t. those two measures
    -- — the área data it does carry is preserved in area_planted_ha/area_harvested_ha,
    -- not lost (DBT-4: intentional; the OK/MISSING_*/INCOMPLETE taxonomy has no
    -- area-only slot, and an area-only row genuinely lacks both qty and value).
    {{ data_quality_flag('qty_native', 'val_raw') }}        as data_quality_flag,
    last_refresh

from enriched
