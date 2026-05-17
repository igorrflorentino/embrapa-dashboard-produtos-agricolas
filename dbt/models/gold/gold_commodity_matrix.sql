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
-- Conventions
--
--  Silver already converts every historical-currency value to present BRL via
--  the `historical_currency_factors` seed (so val_raw is in R$ regardless of
--  the year). Gold only applies FX and inflation deflation on top.
--
--  • val_nominal_*  = val_raw (BRL) converted to USD/EUR/CNY at the FX rate
--                     of THAT year. Use this for historical auditing — note
--                     pre-1994 BRL is purchasing-power-equivalent today, but
--                     the FX rate of the year is in the currency of the year
--                     (Cz$/USD, Cr$/USD, etc.), giving a USD value at the
--                     time the transaction happened.
--
--  • val_real_ipca_* = val_raw projected to today via the IPCA chain (real
--                     inflation only — currency reforms already absorbed in
--                     Silver), then optionally converted to foreign currency
--                     at TODAY's FX rates. This is the column for cross-year
--                     economic comparison.
--
--  • val_real_igpm_* = identical logic to IPCA, using IGP-M.
--
--  NULL semantics:
--    - placeholders (-, ..., *) in the source → NULL in the Silver layer;
--    - missing currency factor for unit_of_measure → NULL val_raw → NULL all monetary;
--    - missing IPCA / IGP-M index for that year → NULL real_* columns;
--    - missing FX rate for that year (e.g. EUR pre-1999) → NULL nominal_FX.
-- ────────────────────────────────────────────────────────────────────────────

with base_pevs as (

    select
        reference_year,
        state_acronym,
        city_name,
        any_value(city_code)            as city_code,
        product_code,
        any_value(product_description)  as product_description,
        max(case when is_quantity_tons  then numeric_value end) as qty_tons,
        max(case when is_quantity_m3    then numeric_value end) as qty_m3,
        max(case when is_monetary_value then numeric_value end) as val_raw,
        max(ingestion_timestamp)        as last_refresh
    from {{ ref('silver_ibge_pevs') }}
    group by reference_year, state_acronym, city_name, product_code
    having qty_tons   is not null
        or qty_m3     is not null
        or val_raw    is not null

),

inflation_year_end as (

    select
        reference_year,
        max(case when series_code = '{{ var("inflation_series_ipca") }}' then index_value end) as ipca_year_end,
        max(case when series_code = '{{ var("inflation_series_igpm") }}' then index_value end) as igpm_year_end
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
        max(case when series_code = '{{ var("inflation_series_ipca") }}' then index_value end) as ipca_current,
        max(case when series_code = '{{ var("inflation_series_igpm") }}' then index_value end) as igpm_current
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
        avg(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_avg,
        avg(case when currency = 'CNY' then brl_per_foreign_unit end) as brl_per_cny_avg
    from {{ ref('silver_bcb_currency') }}
    where brl_per_foreign_unit is not null
    group by reference_year

),

fx_latest as (

    select
        max(case when currency = 'USD' then brl_per_foreign_unit end) as brl_per_usd_current,
        max(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_current,
        max(case when currency = 'CNY' then brl_per_foreign_unit end) as brl_per_cny_current
    from (
        select currency, brl_per_foreign_unit
        from {{ ref('silver_bcb_currency') }}
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
        fy.brl_per_cny_avg,
        iy.ipca_year_end,
        iy.igpm_year_end,
        il.ipca_current,
        il.igpm_current,
        fxl.brl_per_usd_current,
        fxl.brl_per_eur_current,
        fxl.brl_per_cny_current,

        -- Real-IPCA BRL: val_raw is already in present-day BRL (Silver applied
        -- the historical_currency_factors seed); we now apply the IPCA chain
        -- ratio to bring the year-of-record purchasing power up to today.
        b.val_raw * safe_divide(il.ipca_current, iy.ipca_year_end) as val_real_ipca_brl,
        -- Real-IGPM BRL: same logic with the alternative series.
        b.val_raw * safe_divide(il.igpm_current, iy.igpm_year_end) as val_real_igpm_brl

    from base_pevs b
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

    -- ── Quantities ───────────────────────────────────────────────────────────
    qty_tons                                                 as quantity_tons,
    qty_m3                                                   as quantity_m3,

    -- ── Nominal: value as reported, converted via FX of THAT year ────────────
    -- Foreign-currency nominal columns are NULL pre-1994: the FX rate of the
    -- year is in the currency-of-the-year (Cz$/USD etc.), which would mix
    -- units of mass-different scale with current values and confuse readers.
    -- Use val_real_* for cross-year comparisons.
    val_raw                                                  as val_nominal_brl,
    case when reference_year >= 1994
        then safe_divide(val_raw, brl_per_usd_avg) end       as val_nominal_usd,
    case when reference_year >= 1994
        then safe_divide(val_raw, brl_per_eur_avg) end       as val_nominal_eur,
    case when reference_year >= 1994
        then safe_divide(val_raw, brl_per_cny_avg) end       as val_nominal_cny,

    -- ── Real via IPCA: comparable across years, expressed in current units ──
    val_real_ipca_brl                                        as val_real_ipca_brl,
    safe_divide(val_real_ipca_brl, brl_per_usd_current)      as val_real_ipca_usd,
    safe_divide(val_real_ipca_brl, brl_per_eur_current)      as val_real_ipca_eur,
    safe_divide(val_real_ipca_brl, brl_per_cny_current)      as val_real_ipca_cny,

    -- ── Real via IGP-M ───────────────────────────────────────────────────────
    val_real_igpm_brl                                        as val_real_igpm_brl,
    safe_divide(val_real_igpm_brl, brl_per_usd_current)      as val_real_igpm_usd,
    safe_divide(val_real_igpm_brl, brl_per_eur_current)      as val_real_igpm_eur,
    safe_divide(val_real_igpm_brl, brl_per_cny_current)      as val_real_igpm_cny,

    -- ── Quality + provenance ─────────────────────────────────────────────────
    {{ data_quality_flag('qty_tons', 'qty_m3', 'val_raw') }} as data_quality_flag,
    last_refresh

from enriched
