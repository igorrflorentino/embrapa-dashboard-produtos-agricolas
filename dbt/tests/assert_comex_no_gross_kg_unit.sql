-- Tripwire: the gross-weight statistical unit must not silently reach aggregation.
--
-- comex_unit.csv maps co_unid=24 → 'QUILOGRAMA BRUTO' (gross kg), and
-- unit_family_conversions maps that label to family='massa', to_base=0.001 —
-- IDENTICAL to net kg. So if MDIC ever reports an NCM under this statistical unit,
-- its GROSS weight would sum into the same 'massa' base (t) as the net-weight
-- products, silently mixing gross and net. No real MDIC data uses co_unid=24 today
-- (a latent gap, not a live bug), so this test passes now — and WARNS the moment the
-- unit appears, forcing a deliberate decision (a per-product override in the
-- unit_family_conversions crosswalk, or exclusion) before the mixed-weight
-- aggregation reaches Gold. WARN (not error) so a source-data change surfaces
-- loudly without hard-blocking the whole nightly build.
--
-- Fails (returns rows) if silver_comex_flows carries the gross-kg statistical unit.

{{ config(severity='warn') }}

select
    stat_unit_code,
    count(*) as n_rows
from {{ ref('silver_comex_flows') }}
where stat_unit_code = '24'   -- co_unid 24 = QUILOGRAMA BRUTO (gross kg)
group by stat_unit_code
