{{ config(materialized='table') }}

-- ────────────────────────────────────────────────────────────────────────────
-- gold_commodity_crosswalk — cross-source product bridge (RESOLVED to exact codes).
--
-- The same physical commodity wears a different code in each source: PEVS uses
-- an extractive-product code, COMEX an 8-digit NCM, COMTRADE a 6-digit HS. Every
-- cross-source analysis (export coefficient, world market share, price spread,
-- trade mirror, harvest→shipment lag) must join the SAME commodity across them —
-- and that link is domain knowledge, not a SELECT DISTINCT.
--
-- The hand-maintained `commodity_crosswalk` seed encodes that knowledge at the
-- commodity-CONCEPT level: a few code PREFIXES per commodity (e.g. roundwood ↔
-- HS/NCM 4403). This model expands those prefixes against the codes that actually
-- appear in each Gold fact table, emitting exact (source, code) → commodity rows
-- so a consumer joins on equality. A code that matches no prefix is simply absent
-- here → "unlinked" (graceful degradation), never an error.
--
-- Grain: one row per (source, code). source ∈ {pevs, comex, comtrade}.
--
-- ⚠ SEED INVARIANT (load-bearing): within a single source, no commodity's
-- code_prefix may be a prefix of a code that ANOTHER commodity also matches.
-- The join below is `code LIKE prefix || '%'` and the SELECT is only `distinct`
-- (which collapses fully-identical rows, NOT a (source, code) that resolves to
-- two commodity_ids). If two commodities had overlapping prefixes — e.g. one
-- seeds `1201` (soja) and another `12010` (a soja sub-product) — a code like
-- `1201010` would resolve to BOTH, and because the serving marts LEFT JOIN this
-- crosswalk on (source, code), that row would FAN OUT and silently DOUBLE every
-- qty_base/val_* sum for that code. The `dbt_utils.unique_combination_of_columns`
-- test on (source, code) in _gold.yml is the build-time guard that trips if this
-- invariant is ever broken — keep it, and keep seed prefixes non-overlapping.
-- ────────────────────────────────────────────────────────────────────────────

with xwalk as (

    select commodity_id, commodity_name, source, code_prefix
    from {{ ref('commodity_crosswalk') }}

),

source_codes as (

    select distinct 'pevs' as source, product_code as code
    from {{ ref('gold_pevs_production') }}
    union all
    select distinct 'comex' as source, ncm_code as code
    from {{ ref('gold_comex_flows') }}
    union all
    select distinct 'comtrade' as source, cmd_code as code
    from {{ ref('gold_comtrade_flows') }}

)

select distinct
    x.commodity_id,
    x.commodity_name,
    c.source,
    c.code
from source_codes c
join xwalk x
    on c.source = x.source
    and c.code like x.code_prefix || '%'
