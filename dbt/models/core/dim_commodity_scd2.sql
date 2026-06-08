{{
    config(
        materialized='view',
        schema=env_var('BQ_SERVING_DATASET', 'serving'),
        enabled=var('enable_curation', false)
    )
}}

-- ────────────────────────────────────────────────────────────────────────────
-- dim_commodity_scd2 — Slowly Changing Dimension (Type 2) over the researchers'
-- append-only curation log.
--
-- Researchers reclassify commodities (processing_stage: in_natura, beneficiado,
-- semi_processado, industrializado, …) from the dashboard's curation panel. Each
-- "Salvar" appends ONE immutable row to
-- `research_inputs.commodity_processing_stage_log` (written by the Python
-- data-access layer, never by dbt) — the Gold tables are NEVER overwritten.
--
-- This model derives the SCD2 timeline per commodity with a window function:
--   valid_from = edited_at of this version
--   valid_to   = LEAD(edited_at) — the moment the NEXT edit superseded it
--                (NULL for the current version → open interval)
--   is_current = valid_to IS NULL
--
-- Materialized as a VIEW on purpose: the log is small, and a view means a fresh
-- INSERT from the curation panel is visible to the UI immediately, with no dbt
-- rebuild. The dashboard LEFT JOINs the static serving marts to this live dim on
-- `commodity_id` (filter is_current for "now", or `valid_from <= as_of < valid_to`
-- for a point-in-time reconstruction of how a commodity was classified back then).
--
-- Grain: one row per (commodity_id, version).
-- ────────────────────────────────────────────────────────────────────────────

with log as (

    select
        commodity_id,
        processing_stage,
        note,
        edited_by,
        edited_at,
        change_id
    from {{ source('research_inputs', 'commodity_processing_stage_log') }}

),

versioned as (

    select
        commodity_id,
        processing_stage,
        note,
        edited_by,
        edited_at,
        -- Order by edit time, breaking ties on the surrogate change_id so two
        -- edits in the same instant still get a deterministic version sequence.
        row_number() over w  as version,
        lead(edited_at) over w as valid_to
    from log
    window w as (partition by commodity_id order by edited_at, change_id)

)

select
    commodity_id,
    version,
    processing_stage,
    note,
    edited_by,
    edited_at        as valid_from,
    valid_to,
    valid_to is null as is_current
from versioned
