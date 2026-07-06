-- Single-family invariant: each product reports under exactly ONE physical-unit family.
--
-- The IBGE Gold pivots (gold_pevs/pam/ppm_production) lift family/unit/qty via max()
-- under a "one unit family per product" assumption, and the serving readers do
-- any_value(family) + sum(qty_native) per product. If a product ever spanned TWO
-- families — a seed or ingestion error, e.g. castanha ('massa'/t) with a stray
-- 'volume'/m³ row — those sums would blend t + m³ into a nonsense total SILENTLY, with
-- no error, contaminating the product series and the cross-source analytics built on it.
-- The invariant holds in today's data; this pins it against future corruption.
--
-- WARN (not error): surfaces a violation in the build output without hard-blocking the
-- whole prod build. Promote to error / a data_quality_flag tier if in-product visibility
-- is wanted.
--
-- Fails (returns rows) if any (model, product_code) carries more than one distinct family.

{{ config(severity='warn') }}

with prod as (
    select 'gold_pevs_production' as model, product_code, family from {{ ref('gold_pevs_production') }}
    union all
    select 'gold_pam_production',  product_code, family from {{ ref('gold_pam_production') }}
    union all
    select 'gold_ppm_production',  product_code, family from {{ ref('gold_ppm_production') }}
)

select
    model,
    product_code,
    count(distinct family)                      as n_families,
    string_agg(distinct family order by family) as families
from prod
where family is not null
group by model, product_code
having count(distinct family) > 1
