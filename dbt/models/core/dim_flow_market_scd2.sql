{{
    config(
        materialized='view',
        schema=env_var('BQ_SERVING_DATASET', 'serving'),
        enabled=var('enable_curation', false)
    )
}}

-- Researcher-editable (customs procedure × flow) market-nature (consumo/processamento).
-- Like dim_code_industrialization_scd2, this model self-disables via the `enable_curation`
-- flag above, so a prod build must pass `--vars 'enable_curation: true'` to materialize it
-- (and thus the market-nature editor's live reads AND serving_comtrade_annual.market_nature,
-- which LEFT JOINs this view). The market-nature is edit-driven again — reverted from the
-- static comtrade_market_nature seed (v1.9.0) back to the append-log matrix editor.

-- ────────────────────────────────────────────────────────────────────────────
-- dim_flow_market_scd2 — Type-2 SCD over the researchers' append-only
-- (customs procedure × flow) market-nature log. Classifies each
-- (customs_code, flow_code) pair as consumo / processamento (an empty market
-- clears the pair) — the economic-purpose axis the "Finalidade econômica"
-- analysis + the "Tipo de mercado" filter read (as the materialized
-- serving_comtrade_annual.market_nature column).
--
-- Each "Aplicar à base" in the "Tipo de Mercado" matrix appends ONE immutable
-- row to research_inputs.flow_market_log (written by the Python data-access
-- layer, never by dbt). This view derives the timeline per (customs_code, flow_code):
--   valid_from = edited_at of this version
--   valid_to   = LEAD(edited_at) — when the next edit superseded it (NULL = open)
--   is_current = valid_to IS NULL
--
-- Materialized as a VIEW on purpose (mirrors dim_code_industrialization_scd2):
-- the log is small, and a view means a fresh INSERT from the matrix editor is
-- visible to the editor's live read immediately, with no dbt rebuild. The
-- serving mart LEFT JOINs this dim on (customs_code, flow_code) filtered to
-- is_current — the mart's market_nature therefore reflects an edit only after
-- the next dbt build (documented latency; the editor itself is instant).
--
-- `flow_code` carries the NORMALIZED flow token (export/import/re-export/… — the
-- same value serving_comtrade_annual.flow exposes), NOT the raw UN code (X/M/RX),
-- so the mart join `ct.flow = fm.flow_code` binds directly.
--
-- Grain: one row per (customs_code, flow_code, version).
-- ────────────────────────────────────────────────────────────────────────────

with log as (

    select
        customs_code,
        flow_code,
        market,
        edited_by,
        edited_at,
        change_id
    from {{ source('research_inputs', 'flow_market_log') }}

),

versioned as (

    select
        customs_code,
        flow_code,
        market,
        edited_by,
        edited_at,
        -- Order by edit time, breaking ties on the surrogate change_id so two
        -- edits in the same instant still get a deterministic version sequence.
        row_number() over w     as version,
        lead(edited_at) over w  as valid_to
    from log
    window w as (partition by customs_code, flow_code order by edited_at, change_id)

)

select
    customs_code,
    flow_code,
    version,
    market,
    edited_by,
    edited_at        as valid_from,
    valid_to,
    valid_to is null as is_current
from versioned
