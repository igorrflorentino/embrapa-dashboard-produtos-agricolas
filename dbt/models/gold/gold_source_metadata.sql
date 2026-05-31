{{ config(materialized='view') }}

-- ────────────────────────────────────────────────────────────────────────────
-- gold_source_metadata — per-source provenance for the frontend's metadata seam.
--
-- The dashboard reads ALL bank provenance from the backend (dataStore.meta(id) →
-- bancoMeta(id)), never from frontend literals: table name, cadence, coverage,
-- counters and freshness. This view DERIVES them from the Gold fact tables, so a
-- table rename / new cadence / extended coverage / fresh load propagates to the
-- whole UI (hero, Sobre, Saúde, freshness banner) with nothing diverging from the
-- real data. last_refresh doubles as the goldVersion timestamp (isStale).
--
-- One row per source. A view (not a table) so it always reflects the current Gold.
-- NOT here (runtime config, see docs/frontend_data_contract.md): implStatus /
-- visible / preview, and SEFAZ (no Gold table yet → implStatus 'um_dia').
-- ────────────────────────────────────────────────────────────────────────────

select
    'ibge_pevs'                    as source,
    'gold_pevs_production'         as gold_table,
    'annual'                       as cadence,
    min(reference_year)            as year_start,
    max(reference_year)            as year_end,
    count(*)                       as total_rows,
    count(distinct product_code)   as products_total,
    -- real Brazilian UFs only — exclude special trade codes (EX/ND/ZN/MN/RE…),
    -- which have no state_name from the state lookup
    count(distinct case when state_name is not null then state_acronym end) as ufs_total,
    max(last_refresh)              as last_refresh
from {{ ref('gold_pevs_production') }}
having count(*) > 0   -- an empty source emits no metadata row (NULL coverage would fail not_null)

union all

select
    'mdic_comex',
    'gold_comex_flows',
    'monthly',
    min(reference_year),
    max(reference_year),
    count(*),
    count(distinct ncm_code),
    count(distinct case when state_name is not null then state_acronym end),
    max(last_refresh)
from {{ ref('gold_comex_flows') }}
having count(*) > 0

union all

select
    'un_comtrade',
    'gold_comtrade_flows',
    'annual',
    min(reference_year),
    max(reference_year),
    count(*),
    count(distinct cmd_code),
    cast(null as int64),           -- COMTRADE has no Brazilian UF (country↔country)
    max(last_refresh)
from {{ ref('gold_comtrade_flows') }}
having count(*) > 0
