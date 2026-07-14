-- Defensive invariant (WARN, not error): a COMEX NCM should carry exactly ONE native
-- statistical unit. serving_comex_annual sums qty_native grouped by (reference_year, flow,
-- ncm_code, state_acronym, country, family) WITHOUT stat_unit_code in the grain, so if MDIC
-- ever reclassifies an NCM's statistical unit between two SAME-family units (e.g. QUILOGRAMA
-- <-> TONELADA, or MILHEIRO <-> NUMERO — same family, different to_base), the annual rollup
-- would blend the two populations under one any_value(unit_native) label, i.e. a wrong
-- qty_native. It has never happened in the full ingested history, and the productTS quantity
-- chart reads the unit-safe qty_base (sum(qty_base) split by family) rather than qty_native —
-- so this is a latent blind spot, not an active bug. This test converts it into a build-time
-- WARNING the moment MDIC first reclassifies a unit, so the operator adds the stat-unit
-- dimension to the serving grain before any blended quantity can surface (e.g. in the Dados
-- row inspector). WARN (not error) so the known-clean state never hard-blocks the prod build.
--
-- Fails (returns rows) if any ncm_code reports under more than one distinct unit_native.

{{ config(severity='warn') }}

select
    ncm_code,
    count(distinct unit_native)             as n_units,
    string_agg(distinct unit_native, ', ')  as units
from {{ ref('gold_comex_flows') }}
where unit_native is not null
group by ncm_code
having count(distinct unit_native) > 1
