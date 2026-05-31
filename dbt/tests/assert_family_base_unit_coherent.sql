-- Coherence guard for the physical-unit family columns across every Gold table.
--
-- `family` and `base_unit` are a pair: each family has exactly one base unit
-- (massa→t, volume→m³, energia→MWh, contagem→un, area→ha) and 'desconhecida'
-- carries no base. When Gold aggregates a grain that summed over multiple source
-- statistical units, picking `family` and `base_unit` with INDEPENDENT any_value()s
-- can pair them from different rows (e.g. family='desconhecida' with base_unit='t').
-- gold_comex_flows and gold_comtrade_flows therefore pick the unit fields together
-- from the dominant-quantity row; this test pins that invariant so a future edit
-- can't reintroduce the mismatch.
--
-- Fails (returns rows) if any Gold row pairs a family with the wrong base_unit.

with valid as (
    select 'massa' as family,    't'   as base_unit union all
    select 'volume',             'm³'         union all
    select 'energia',            'MWh'        union all
    select 'contagem',           'un'         union all
    select 'area',               'ha'
),

gold as (
    select 'gold_pevs_production' as model, family, base_unit from {{ ref('gold_pevs_production') }}
    union all
    select 'gold_comex_flows',    family, base_unit from {{ ref('gold_comex_flows') }}
    union all
    select 'gold_comtrade_flows', family, base_unit from {{ ref('gold_comtrade_flows') }}
)

select g.model, g.family, g.base_unit
from gold g
left join valid v using (family)
where
    -- family must never be NULL — it would make both branches below evaluate to
    -- NULL and slip through; every Gold row carries at least 'desconhecida'
    g.family is null
    -- desconhecida must carry no base unit
    or (g.family = 'desconhecida' and g.base_unit is not null)
    -- a real family must carry exactly its canonical base unit
    or (g.family != 'desconhecida' and g.base_unit is distinct from v.base_unit)
