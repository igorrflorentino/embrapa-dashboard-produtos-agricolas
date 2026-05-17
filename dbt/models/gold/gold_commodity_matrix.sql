{{
    config(
        materialized='incremental',
        incremental_strategy='insert_overwrite',
        unique_key=['reference_year', 'state_acronym', 'city_name', 'product_code'],
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
--  • val_nominal_*  = the raw IBGE amount in the currency of its own year,
--                     converted to USD/EUR/CNY using FX rates of THAT year.
--                     For BRL: kept as reported (Cruzeiros, Cruzados, Reais...).
--                     Use this for historical auditing only.
--
--  • val_real_ipca_* = raw amount projected to today via the IPCA chain-link
--                     (which absorbs both inflation and every Brazilian
--                     currency reform), then optionally converted to
--                     foreign currency at TODAY's FX rates.
--                     This is the column for cross-year economic comparison.
--
--  • val_real_igpm_* = identical logic to IPCA, using IGP-M.
--
--  NULL semantics:
--    - placeholders (-, ..., *) in the source → NULL in the Silver layer;
--    - missing IPCA / IGP-M index for that year → NULL real_* columns;
--    - missing FX rate for that year (e.g. EUR pre-1999) → NULL nominal_FX.
-- ────────────────────────────────────────────────────────────────────────────

with base_pevs as (

    select
        reference_year,
        state_acronym,
        city_name,
        product_code,
        any_value(product_description) as product_description,
        max(case when is_quantity_tons  then numeric_value end) as qty_tons,
        max(case when is_quantity_m3    then numeric_value end) as qty_m3,
        max(case when is_monetary_value then numeric_value end) as val_raw
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

        -- Real-IPCA BRL: chain-linked deflator absorbs inflation + monetary reforms.
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
    reference_year,
    state_acronym,
    city_name,
    product_description,
    product_code,

    -- ── Quantities ────────────────────────────────────────────────────────────
    qty_tons * 1000.0                                       as quantitykg,
    qty_tons                                                 as quantitytons,
    qty_m3                                                   as quantitym3,
    qty_m3   * 1000.0                                       as quantityliters,

    -- ── Nominal: value as reported, converted via FX of THAT year ───────────
    val_raw                                                  as valnominalbrl,
    safe_divide(val_raw, brl_per_usd_avg)                    as valnominalusd,
    safe_divide(val_raw, brl_per_eur_avg)                    as valnominaleur,
    safe_divide(val_raw, brl_per_cny_avg)                    as valnominalcny,

    -- ── Real via IPCA: comparable across years, expressed in current units ─
    val_real_ipca_brl                                        as valrealipcabrl,
    safe_divide(val_real_ipca_brl, brl_per_usd_current)      as valrealipcausd,
    safe_divide(val_real_ipca_brl, brl_per_eur_current)      as valrealipcaeur,
    safe_divide(val_real_ipca_brl, brl_per_cny_current)      as valrealipcacny,

    -- ── Real via IGP-M ─────────────────────────────────────────────────────
    val_real_igpm_brl                                        as valrealigpmbrl,
    safe_divide(val_real_igpm_brl, brl_per_usd_current)      as valrealigpmusd,
    safe_divide(val_real_igpm_brl, brl_per_eur_current)      as valrealigpmeur,
    safe_divide(val_real_igpm_brl, brl_per_cny_current)      as valrealigpmcny,

    {{ data_quality_flag(
        'qty_tons * 1000.0',
        'qty_tons',
        'qty_m3',
        'qty_m3 * 1000.0',
        'val_raw'
    ) }} as dataquality_flag

from enriched

{% if is_incremental() %}
    where reference_year in (select distinct reference_year from {{ ref('silver_ibge_pevs') }})
{% endif %}
