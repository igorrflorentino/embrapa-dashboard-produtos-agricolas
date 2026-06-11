-- Singular test: the US$ value must be CONSERVED across the Silver→Gold
-- aggregation for the trade sources (COMEX, COMTRADE).
--
-- gold_<trade> builds a `base_flows` CTE that GROUP BYs the Silver source grain
-- and SUMs the nominal US$ measure (val_fob_usd / primary_value_usd), then
-- re-exposes that sum verbatim as `val_yearfx_usd` (USD = identity, no FX
-- applied). No row is filtered between the two layers. So the grand total US$
-- must be IDENTICAL on both sides — only the grain got coarser.
--
-- A drift means the Silver→Gold step silently changed the money: most likely a
-- reference-seed LEFT JOIN (comex_ncm / comex_country / comex_via / comtrade_hs
-- / comtrade_country) fanned out on a DUPLICATE key and multiplied value across
-- the duplicates. That is the same class of silent corruption as the COMTRADE
-- ~2.5x double-count (#52) — caught here as an inflated gold_total. (The grain
-- uniqueness tests do NOT catch this: the fan-out happens after the GROUP BY,
-- inside the dimension join, so the grain stays unique while the value inflates.)
--
-- NULLs are ignored consistently on both sides (SUM skips them; an all-NULL
-- group yields a NULL gold value that SUM also skips). The tolerance is RELATIVE
-- (1e-6 = one part per million) because float64 summation is non-associative —
-- the two sides aggregate in different orders, so they may differ by rounding
-- noise (~1e-10 relative) even when mathematically equal. Any real fan-out moves
-- the total by whole percent, far above the threshold.
--
-- Fails (returns a row) when |gold_total - silver_total| exceeds 1e-6 of the
-- Silver total, per source.

with checks as (

    select
        'mdic_comex'                                                        as source,
        (select sum(val_fob_usd)     from {{ ref('silver_comex_flows') }})  as silver_total_usd,
        (select sum(val_yearfx_usd)  from {{ ref('gold_comex_flows') }})    as gold_total_usd

    union all

    select
        'un_comtrade',
        (select sum(primary_value_usd) from {{ ref('silver_comtrade_flows') }}),
        (select sum(val_yearfx_usd)    from {{ ref('gold_comtrade_flows') }})

)

select
    source,
    silver_total_usd,
    gold_total_usd,
    gold_total_usd - silver_total_usd                            as drift_usd,
    safe_divide(gold_total_usd - silver_total_usd, silver_total_usd) as drift_fraction
from checks
where silver_total_usd is not null
  and abs(coalesce(gold_total_usd, 0) - silver_total_usd) > abs(silver_total_usd) * 1e-6
