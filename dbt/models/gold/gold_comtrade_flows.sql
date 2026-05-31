{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1960, 'end': 2050, 'interval': 1}
        },
        cluster_by=['flow', 'cmd_code', 'reporter_code', 'partner_code']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- gold_comtrade_flows — the single comprehensive `flows` table for UN Comtrade
-- (naming: gold_<fonte>_<forma>; `flows` = origin→destination trade). The global
-- complement to gold_comex_flows (Brazil-only).
--
-- Grain: one row per (flow, reference_year, reporter_code, partner_code,
-- cmd_code). The Silver source grain (which also splits by partner2 / customs /
-- mode-of-supply / mode-of-transport / qty-unit) is summed up to this grain.
-- Coarser cuts (by region, by chapter, reporter totals) are derived at query
-- time via GROUP BY — ONE comprehensive table per source. The World partner
-- (partner_code='0') is already dropped in Silver, so SUM over partner_code is
-- a true bilateral total with no double counting.
--
-- Geography is bilateral: for exports reporter=origin, partner=destination;
-- for imports reporter=destination, partner=origin. Both resolve to name + ISO3
-- via comtrade_country.
--
-- Monetary conventions (mirror gold_comex_flows — source value is nominal US$,
-- but annual, so FX is the year average and inflation the year-end index like
-- gold_pevs_production):
--   • val_yearfx_*   = primary_value_usd converted at THAT year's avg FX. usd is
--                      the source value; brl/eur/cny triangulate through BRL.
--                      Nominal — no inflation correction.
--   • val_real_{ipca,igpm,igpdi}_* = USD → BRL at the year FX → projected to today
--                      via the BCB chain index → optionally reconverted to
--                      USD/EUR/CNY at TODAY's FX. Use these for cross-year comparison.
--
-- NULL semantics: missing year FX (EUR pre-1999, CNY pre-2004) → NULL that
-- currency's columns; missing year inflation index → NULL the real_* columns;
-- chapter-44 rows with no reported quantity → NULL qty_native/qty_base/weight.
-- ────────────────────────────────────────────────────────────────────────────

with base_flows as (

    select
        flow,
        reference_year,
        reporter_code,
        partner_code,
        cmd_code,
        any_value(hs_chapter)                     as hs_chapter,
        any_value(qty_unit_code)                  as qty_unit_code,
        any_value(unit_native)                    as unit_native,
        any_value(unit_native_symbol)             as unit_native_symbol,
        any_value(family)                         as family,
        any_value(base_unit)                      as base_unit,
        sum(qty_native)                           as qty_native,
        sum(qty_base)                             as qty_base,
        sum(net_weight_kg)                        as net_weight_kg,
        sum(gross_weight_kg)                      as gross_weight_kg,
        sum(primary_value_usd)                    as primary_value_usd,
        sum(cif_value_usd)                        as cif_value_usd,
        sum(fob_value_usd)                        as fob_value_usd,
        count(*)                                  as source_rows,
        max(ingestion_timestamp)                  as last_refresh
    from {{ ref('silver_comtrade_flows') }}
    group by flow, reference_year, reporter_code, partner_code, cmd_code

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
        avg(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_avg,
        avg(case when currency = 'CNY' then brl_per_foreign_unit end) as brl_per_cny_avg
    from {{ ref('silver_currency') }}
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
        fy.brl_per_cny_avg,
        fxl.brl_per_usd_current,
        fxl.brl_per_eur_current,
        fxl.brl_per_cny_current,

        -- Nominal BRL at the year-average FX (US$ → R$ of that year).
        b.primary_value_usd * fy.brl_per_usd_avg                                              as val_nominal_brl,
        -- Real BRL today: nominal BRL projected forward via each inflation chain.
        (b.primary_value_usd * fy.brl_per_usd_avg) * safe_divide(il.ipca_current,  iy.ipca_year_end)   as val_real_ipca_brl,
        (b.primary_value_usd * fy.brl_per_usd_avg) * safe_divide(il.igpm_current,  iy.igpm_year_end)   as val_real_igpm_brl,
        (b.primary_value_usd * fy.brl_per_usd_avg) * safe_divide(il.igpdi_current, iy.igpdi_year_end)  as val_real_igpdi_brl

    from base_flows b
    left join fx_year            fy  on b.reference_year = fy.reference_year
    left join inflation_year_end iy  on b.reference_year = iy.reference_year
    cross join inflation_latest  il
    cross join fx_latest         fxl

)

select
    -- ── Time ─────────────────────────────────────────────────────────────────
    reference_year,
    date(reference_year, 12, 31)                            as reference_date,

    -- ── Flow direction ───────────────────────────────────────────────────────
    flow,

    -- ── Product (HS) ─────────────────────────────────────────────────────────
    enriched.cmd_code,
    hs_chapter,
    h.description                                           as cmd_description,

    -- ── Geography (bilateral; reporter→partner) ──────────────────────────────
    reporter_code,
    rc.country_name                                         as reporter_name,
    rc.iso_a3                                               as reporter_iso_a3,
    partner_code,
    pc.country_name                                         as partner_name,
    pc.iso_a3                                               as partner_iso_a3,
    pc.is_group                                             as partner_is_group,

    -- ── Quantities (physical-unit family) ───────────────────────────────────
    -- The reported quantity unit varies by HS code (kg, m³, items, …) and is
    -- normalised to a per-family base unit. NEVER sum qty_base across families:
    -- any SUM(qty_base) must GROUP BY family. net_weight_kg is always kilograms
    -- (massa) — a parallel, always-comparable weight. Chapter-44 rows usually
    -- report neither (→ all NULL): see data_quality_flag.
    family,
    qty_unit_code,
    unit_native,
    unit_native_symbol,
    qty_native,
    qty_base,
    base_unit,
    net_weight_kg,
    gross_weight_kg,

    -- ── Year-FX (nominal, at the year-average FX) ────────────────────────────
    primary_value_usd                                      as val_yearfx_usd,
    val_nominal_brl                                        as val_yearfx_brl,
    safe_divide(val_nominal_brl, brl_per_eur_avg)          as val_yearfx_eur,
    safe_divide(val_nominal_brl, brl_per_cny_avg)          as val_yearfx_cny,

    -- ── Real via IPCA (comparable across years, in today's units) ────────────
    val_real_ipca_brl                                      as val_real_ipca_brl,
    safe_divide(val_real_ipca_brl, brl_per_usd_current)    as val_real_ipca_usd,
    safe_divide(val_real_ipca_brl, brl_per_eur_current)    as val_real_ipca_eur,
    safe_divide(val_real_ipca_brl, brl_per_cny_current)    as val_real_ipca_cny,

    -- ── Real via IGP-M ───────────────────────────────────────────────────────
    val_real_igpm_brl                                      as val_real_igpm_brl,
    safe_divide(val_real_igpm_brl, brl_per_usd_current)    as val_real_igpm_usd,
    safe_divide(val_real_igpm_brl, brl_per_eur_current)    as val_real_igpm_eur,
    safe_divide(val_real_igpm_brl, brl_per_cny_current)    as val_real_igpm_cny,

    -- ── Real via IGP-DI ──────────────────────────────────────────────────────
    val_real_igpdi_brl                                     as val_real_igpdi_brl,
    safe_divide(val_real_igpdi_brl, brl_per_usd_current)   as val_real_igpdi_usd,
    safe_divide(val_real_igpdi_brl, brl_per_eur_current)   as val_real_igpdi_eur,
    safe_divide(val_real_igpdi_brl, brl_per_cny_current)   as val_real_igpdi_cny,

    -- ── CIF / FOB split (nominal US$, where the reporter provides it) ────────
    cif_value_usd                                          as val_cif_usd,
    fob_value_usd                                          as val_fob_usd,

    -- ── Quality + provenance ─────────────────────────────────────────────────
    -- "Has a quantity" = any of native qty / net weight present (chapter 44
    -- frequently reports neither → MISSING_QUANTITY, which is expected).
    {{ data_quality_flag('coalesce(qty_native, net_weight_kg)', 'val_nominal_brl') }} as data_quality_flag,
    source_rows,
    last_refresh

from enriched
-- Reference dimensions → human-readable labels for Looker.
left join {{ ref('comtrade_hs') }}      h  on enriched.cmd_code      = h.cmd_code
left join {{ ref('comtrade_country') }} rc on enriched.reporter_code = rc.m49_code
left join {{ ref('comtrade_country') }} pc on enriched.partner_code  = pc.m49_code
