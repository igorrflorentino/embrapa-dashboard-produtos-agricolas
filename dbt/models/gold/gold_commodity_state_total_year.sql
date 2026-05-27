{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['state_acronym', 'region']
    )
}}

-- Geographic-only roll-up: one row per (reference_year, state_acronym),
-- aggregated across ALL products and ALL municipalities. ~1k rows total
-- (~40 years × 27 UFs) — sized to feed the dashboard's Geography view
-- without runtime product-aggregation: choropleths, regional rankings,
-- concentration KPIs (HHI / top-N share), state-level totals.
--
-- Position in the Gold DAG: a sibling of gold_commodity_state_year and
-- gold_commodity_year_product (all three derive in parallel from
-- gold_commodity_matrix). Three roll-ups, three views into the same fact:
--
--   • gold_commodity_year_product   = (year × product) — national time-series
--   • gold_commodity_state_year     = (year × state × product) — exec dashboards
--   • gold_commodity_state_total_year = (year × state) — pure geography
--
-- Drill-down to product breakdown → gold_commodity_state_year. Drill-down
-- to municipal grain → gold_commodity_matrix.

select
    reference_year,
    reference_date,
    state_acronym,
    state_name,
    region,

    -- ── Quantities (sum across cities AND products) ──────────────────────
    sum(quantity_tons) as quantity_tons,
    sum(quantity_m3)   as quantity_m3,

    -- ── Year-FX (foreign columns NULL pre-1994 for the same reason as upstream) ──
    sum(val_yearfx_brl) as val_yearfx_brl,
    sum(val_yearfx_usd) as val_yearfx_usd,
    sum(val_yearfx_eur) as val_yearfx_eur,
    sum(val_yearfx_cny) as val_yearfx_cny,

    -- ── Real via IPCA ────────────────────────────────────────────────────
    sum(val_real_ipca_brl) as val_real_ipca_brl,
    sum(val_real_ipca_usd) as val_real_ipca_usd,
    sum(val_real_ipca_eur) as val_real_ipca_eur,
    sum(val_real_ipca_cny) as val_real_ipca_cny,

    -- ── Real via IGP-M ───────────────────────────────────────────────────
    sum(val_real_igpm_brl) as val_real_igpm_brl,
    sum(val_real_igpm_usd) as val_real_igpm_usd,
    sum(val_real_igpm_eur) as val_real_igpm_eur,
    sum(val_real_igpm_cny) as val_real_igpm_cny,

    -- ── Real via IGP-DI ──────────────────────────────────────────────────
    sum(val_real_igpdi_brl) as val_real_igpdi_brl,
    sum(val_real_igpdi_usd) as val_real_igpdi_usd,
    sum(val_real_igpdi_eur) as val_real_igpdi_eur,
    sum(val_real_igpdi_cny) as val_real_igpdi_cny,

    -- ── Coverage ─────────────────────────────────────────────────────────
    -- distinct counts only: summing n_municipalities_* from state_year would
    -- double-count cities that produce multiple commodities. The dashboard
    -- KPI "Municípios produtores" needs distinct cardinality.
    count(distinct city_name)                                              as n_municipalities_total,
    count(distinct case when data_quality_flag = 'OK' then city_name end)  as n_municipalities_ok,
    count(distinct product_code)                                           as n_products,

    -- ── Provenance ───────────────────────────────────────────────────────
    max(last_refresh) as last_refresh

from {{ ref('gold_commodity_matrix') }}
group by reference_year, reference_date, state_acronym, state_name, region
