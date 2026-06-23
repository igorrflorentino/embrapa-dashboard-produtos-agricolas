-- ────────────────────────────────────────────────────────────────────────────
-- dim_geo_municipio — conformed municipality dimension for Brazil (~5570 rows).
--
-- One row per IBGE município (7-digit city_code — the SIDRA n6 code Gold already
-- carries), mapping it to BOTH IBGE sub-UF divisions. The two divisions do NOT
-- nest into each other (a microrregião and a região imediata are independent
-- partitions of the UF), so the dashboard treats them as parallel facets:
--   • classic census : mesorregião (meso_*) → microrregião (micro_*) → município
--   • current (2017)  : região intermediária (intermediaria_*) → região imediata
--                       (imediata_*) → município
-- plus the shared UF + grande região (macrorregião = the existing `region`).
--
-- Single source of truth for the sub-UF + live-município geography filters: the
-- serving município cube joins gold_<source>_production on city_code to carry
-- these codes through to the SPA's geo cascade. Sourced from the
-- ibge_municipio_mesh seed (scripts/refresh_ibge_municipio_mesh.py).
--
-- meso_*/micro_* are BLANK for a município created after the classic division was
-- frozen (e.g. Boa Esperança do Norte/MT, 2023) — it is still filterable by the
-- 2017 levels and rolls up to its UF; only the classic facet skips it.
--
-- Grain: one row per município. PK = city_code.
-- ────────────────────────────────────────────────────────────────────────────

select
    city_code,
    city_name,
    uf_code,
    state_acronym,
    state_name,
    region_code,
    region_abbrev,
    region_name,
    -- classic census division (legacy)
    meso_code,
    meso_name,
    micro_code,
    micro_name,
    -- current division (2017)
    intermediaria_code,
    intermediaria_name,
    imediata_code,
    imediata_name
from {{ ref('ibge_municipio_mesh') }}
