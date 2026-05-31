{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['flow', 'ncm_code', 'country_code', 'state_acronym']
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- gold_comex_flows — the single comprehensive `flows` table for MDIC Comex Stat
-- (naming: gold_<fonte>_<forma>; `flows` = origin→destination trade).
--
-- Grain: one row per (flow, reference_year, reference_month, ncm_code,
-- country_code, state_acronym). The Silver source grain (which also splits by
-- transport route / customs office / statistical unit) is summed up to this
-- grain here. Any coarser aggregation (annual, national, by-chapter) is derived
-- at query time via GROUP BY — ONE comprehensive table per source.
--
-- Monetary conventions (mirror gold_pevs_production, but the source value
-- VL_FOB is nominal **US$** at the month of record — the opposite direction
-- from PEVS, whose val_raw is BRL):
--
--  • val_yearfx_*   = VL_FOB converted at the FX rate of THAT month. usd is the
--                     source value itself; brl/eur/cny triangulate through BRL.
--                     Nominal — no inflation correction.
--  • val_real_{ipca,igpm,igpdi}_* = VL_FOB → BRL at the month FX → projected to
--                     today via the respective BCB chain index → optionally
--                     reconverted to USD/EUR/CNY at TODAY's FX. Use these for
--                     cross-year comparison.
--
--  NULL semantics: missing month FX (e.g. EUR pre-1999) → NULL that currency's
--  columns; missing month inflation index → NULL the real_* columns;
--  non-Brazilian / special UF codes (EX, ND, ZN, …) → NULL state_name/region.
-- ────────────────────────────────────────────────────────────────────────────

with base_flows as (

    select
        flow,
        reference_year,
        reference_month,
        date(reference_year, reference_month, 1)  as reference_date,
        ncm_code,
        any_value(hs_chapter)                     as hs_chapter,
        country_code,
        state_acronym,
        transport_route_code,
        -- Pick the unit fields together from the group's dominant-quantity row
        -- (same ORDER BY for all five) so family/base_unit/unit stay COHERENT even
        -- when one NCM is reported under mixed statistical units in the same cell.
        array_agg(stat_unit_code order by qty_native desc nulls last, stat_unit_code limit 1)[offset(0)]      as stat_unit_code,
        array_agg(unit_native order by qty_native desc nulls last, stat_unit_code limit 1)[offset(0)]         as unit_native,
        array_agg(unit_native_symbol order by qty_native desc nulls last, stat_unit_code limit 1)[offset(0)]  as unit_native_symbol,
        array_agg(family order by qty_native desc nulls last, stat_unit_code limit 1)[offset(0)]              as family,
        array_agg(base_unit order by qty_native desc nulls last, stat_unit_code limit 1)[offset(0)]           as base_unit,
        sum(qty_native)                           as qty_native,
        sum(qty_base)                             as qty_base,
        sum(net_weight_kg)                        as net_weight_kg,
        sum(val_fob_usd)                          as val_fob_usd,
        sum(freight_usd)                          as freight_usd,
        sum(insurance_usd)                        as insurance_usd,
        count(*)                                  as source_rows,
        max(ingestion_timestamp)                  as last_refresh
    from {{ ref('silver_comex_flows') }}
    group by
        flow, reference_year, reference_month, ncm_code, country_code,
        state_acronym, transport_route_code

),

fx_month as (

    select
        reference_year,
        reference_month,
        avg(case when currency = 'USD' then brl_per_foreign_unit end) as brl_per_usd_avg,
        avg(case when currency = 'EUR' then brl_per_foreign_unit end) as brl_per_eur_avg,
        avg(case when currency = 'CNY' then brl_per_foreign_unit end) as brl_per_cny_avg
    from {{ ref('silver_currency') }}
    where brl_per_foreign_unit is not null
    group by reference_year, reference_month

),

inflation_month as (

    select
        reference_year,
        reference_month,
        max(case when series_code = '{{ var("inflation_series_ipca")  }}' then index_value end) as ipca_index,
        max(case when series_code = '{{ var("inflation_series_igpm")  }}' then index_value end) as igpm_index,
        max(case when series_code = '{{ var("inflation_series_igpdi") }}' then index_value end) as igpdi_index
    from {{ ref('silver_bcb_inflation') }}
    where index_value is not null
    group by reference_year, reference_month

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
        fm.brl_per_usd_avg,
        fm.brl_per_eur_avg,
        fm.brl_per_cny_avg,
        fxl.brl_per_usd_current,
        fxl.brl_per_eur_current,
        fxl.brl_per_cny_current,

        -- Nominal BRL at the month-of-record FX (US$ FOB → R$ of that month).
        b.val_fob_usd * fm.brl_per_usd_avg                                            as val_nominal_brl,
        -- Real BRL today: nominal BRL projected forward via each inflation chain.
        (b.val_fob_usd * fm.brl_per_usd_avg) * safe_divide(il.ipca_current,  im.ipca_index)  as val_real_ipca_brl,
        (b.val_fob_usd * fm.brl_per_usd_avg) * safe_divide(il.igpm_current,  im.igpm_index)  as val_real_igpm_brl,
        (b.val_fob_usd * fm.brl_per_usd_avg) * safe_divide(il.igpdi_current, im.igpdi_index) as val_real_igpdi_brl

    from base_flows b
    left join fx_month        fm  on b.reference_year = fm.reference_year and b.reference_month = fm.reference_month
    left join inflation_month im  on b.reference_year = im.reference_year and b.reference_month = im.reference_month
    cross join inflation_latest il
    cross join fx_latest        fxl

)

select
    -- ── Time ─────────────────────────────────────────────────────────────────
    reference_year,
    reference_month,
    reference_date,

    -- ── Flow direction ───────────────────────────────────────────────────────
    flow,

    -- ── Product (HS / NCM) ───────────────────────────────────────────────────
    ncm_code,
    hs_chapter,
    n.ncm_description                                        as ncm_description,

    -- ── Geography ────────────────────────────────────────────────────────────
    -- country_code is the MDIC numeric code; state_acronym is the UF of the NCM
    -- (special non-UF codes like EX/ND/ZN keep their raw value, NULL name/region).
    country_code,
    c.country_name                                          as country_name,
    c.iso_a3                                                 as country_iso_a3,
    state_acronym,
    {{ state_name('state_acronym') }}                        as state_name,
    {{ state_region('state_acronym') }}                      as region,

    -- ── Transport mode (MDIC CO_VIA) ─────────────────────────────────────────
    transport_route_code,
    v.via_name                                              as via_name,

    -- ── Quantities (physical-unit family) ───────────────────────────────────
    -- The NCM statistical quantity is reported in a unit that varies by product
    -- (kg, m³, litro, número, …). It is normalised to a per-family base unit:
    --   family       — massa | volume | energia | contagem | area | desconhecida
    --   unit_native  — the source statistical-unit label (for display/audit)
    --   qty_native   — the value in unit_native
    --   qty_base     — qty_native converted to base_unit (t / m³ / MWh / un / ha)
    --   base_unit    — the family's base unit
    -- NEVER sum qty_base across families: any SUM(qty_base) must GROUP BY family
    -- (build the q_by_family map at query time). net_weight_kg is always
    -- kilograms (massa) — a parallel, always-comparable weight measure.
    family,
    stat_unit_code,
    unit_native,
    unit_native_symbol,
    qty_native,
    qty_base,
    base_unit,
    net_weight_kg,

    -- ── Year-FX (nominal, at the month-of-record FX) ─────────────────────────
    val_fob_usd                                             as val_yearfx_usd,
    val_nominal_brl                                         as val_yearfx_brl,
    safe_divide(val_nominal_brl, brl_per_eur_avg)           as val_yearfx_eur,
    safe_divide(val_nominal_brl, brl_per_cny_avg)           as val_yearfx_cny,

    -- ── Real via IPCA (comparable across years, expressed in today's units) ──
    val_real_ipca_brl                                       as val_real_ipca_brl,
    safe_divide(val_real_ipca_brl, brl_per_usd_current)     as val_real_ipca_usd,
    safe_divide(val_real_ipca_brl, brl_per_eur_current)     as val_real_ipca_eur,
    safe_divide(val_real_ipca_brl, brl_per_cny_current)     as val_real_ipca_cny,

    -- ── Real via IGP-M ───────────────────────────────────────────────────────
    val_real_igpm_brl                                       as val_real_igpm_brl,
    safe_divide(val_real_igpm_brl, brl_per_usd_current)     as val_real_igpm_usd,
    safe_divide(val_real_igpm_brl, brl_per_eur_current)     as val_real_igpm_eur,
    safe_divide(val_real_igpm_brl, brl_per_cny_current)     as val_real_igpm_cny,

    -- ── Real via IGP-DI ──────────────────────────────────────────────────────
    val_real_igpdi_brl                                      as val_real_igpdi_brl,
    safe_divide(val_real_igpdi_brl, brl_per_usd_current)    as val_real_igpdi_usd,
    safe_divide(val_real_igpdi_brl, brl_per_eur_current)    as val_real_igpdi_eur,
    safe_divide(val_real_igpdi_brl, brl_per_cny_current)    as val_real_igpdi_cny,

    -- ── Freight / insurance (nominal US$, import-only; NULL/0 on export) ─────
    freight_usd                                             as val_freight_usd,
    insurance_usd                                           as val_insurance_usd,

    -- ── Quality + provenance ─────────────────────────────────────────────────
    case
        when val_fob_usd is null and net_weight_kg is null then 'INCOMPLETE'
        when val_fob_usd is null                           then 'MISSING_VALUE'
        when net_weight_kg is null                         then 'MISSING_WEIGHT'
        else 'OK'
    end                                                     as data_quality_flag,
    source_rows,
    last_refresh

from enriched
-- Reference dimensions (MDIC aux tables) → human-readable labels for Looker.
-- (The statistical-unit label + family are resolved upstream in Silver.)
left join {{ ref('comex_ncm') }}     n on enriched.ncm_code            = n.co_ncm
left join {{ ref('comex_country') }} c on enriched.country_code        = c.co_pais
left join {{ ref('comex_via') }}     v on enriched.transport_route_code = v.co_via
