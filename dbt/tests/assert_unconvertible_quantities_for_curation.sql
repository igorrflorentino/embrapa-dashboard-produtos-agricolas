-- Curation surface (WARN, not error): quantity readings that carry a value but
-- could NOT be normalised to a family base unit (qty_base IS NULL while a
-- qty_native exists). Two legitimate causes, both needing human action:
--   1. family = 'desconhecida' — the source unit isn't in the 5 families; add a
--      row to unit_family_conversions (or decide it's genuinely out of scope).
--   2. a commodity unit (saca/@/bushel/barril) without a product_unit_factors
--      row — supply the per-product to_base.
-- We never invent a conversion, so these rows ship with qty_base NULL; this
-- test keeps them visible instead of letting them vanish silently.
{{ config(severity='warn') }}

select 'gold_pevs_production' as model, family, unit_native, count(*) as n
from {{ ref('gold_pevs_production') }}
where qty_native is not null and qty_base is null
group by 1, 2, 3

union all

select 'gold_comex_flows' as model, family, unit_native, count(*) as n
from {{ ref('gold_comex_flows') }}
where qty_native is not null and qty_base is null
group by 1, 2, 3
