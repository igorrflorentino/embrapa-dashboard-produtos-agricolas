{{ config(materialized='view') }}

-- ────────────────────────────────────────────────────────────────────────────
-- dim_commodity_catalog — the CURRENT commodity catalog (Curadoria).
--
-- The editable successor to the version-controlled `commodity_crosswalk` seed: the
-- researcher-managed catalog of which commodities are in the dashboard and their
-- agrupamento (cross-source concept). Each commodity is registered by its EXACT
-- source code (`codigo_commodity`; no prefixes). Written append-only by the
-- dashboard's admin editor (the Python data-access layer, never dbt) to
-- research_inputs.commodity_catalog_log; this view derives the CURRENT catalog = the
-- latest row per (codigo_commodity, banco), keeping only active rows (a row with
-- active=false is a tombstone — the entry has LEFT the catalog, so its Gold data
-- becomes an orphan, handled non-destructively downstream).
--
-- Exposes (commodity_id, commodity_name, source, codigo_commodity) — the consumers
-- (gold_commodity_crosswalk + serving_{pam,ppm}_annual) join on `code = codigo_commodity`
-- (equality; no LIKE-prefix expansion).
--
-- Materialized as a VIEW on purpose: the log is small and a fresh admin edit is then
-- visible to the next build / request immediately, with no rebuild.
--
-- NOT gated by enable_curation (unlike dim_code_industrialization_scd2): this is the
-- LIVE catalog the gold model reads — it must exist. The source table is created on
-- the first write / the cutover backfill; a fresh project must backfill it (fail loud
-- if absent — never silently fall back to the retired seed).
--
-- ⚠ Grain: one row per (codigo_commodity, banco). Because every code is exact (no
-- prefixes), a Gold code resolves to AT MOST one commodity, so the cross-source join
-- cannot fan out — guarded at build time by the unique_combination_of_columns(source,
-- code) test on gold_commodity_crosswalk.
-- ────────────────────────────────────────────────────────────────────────────

with log as (

    select
        codigo_commodity,
        banco,
        agrupamento,
        descricao_commodity,
        ciclo_de_vida,
        commodity_id,
        active,
        edited_by,
        edited_at,
        change_id
    from {{ source('research_inputs', 'commodity_catalog_log') }}

),

current_catalog as (

    select
        *,
        row_number() over (
            partition by codigo_commodity, banco
            order by edited_at desc, change_id desc
        ) as _rn
    from log

)

select
    commodity_id,
    agrupamento     as commodity_name,
    banco           as source,
    codigo_commodity,
    descricao_commodity,
    ciclo_de_vida,
    edited_by,
    edited_at
from current_catalog
where _rn = 1 and active
