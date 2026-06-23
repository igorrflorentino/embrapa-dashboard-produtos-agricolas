-- Singular test: the value total must be CONSERVED across Gold→serving.
--
-- Each serving_*_annual mart rolls its Gold fact up to a coarser grain with plain
-- SUM(...) and then LEFT JOINs the conformed dims (dim_geo_br) + the
-- gold_commodity_crosswalk. A clean roll-up + 1:1 joins must leave the grand total
-- unchanged. The likeliest way it WOULDN'T: a duplicate (source, code) row in the
-- crosswalk (or a dim) fans the LEFT JOIN out and silently INFLATES the served
-- total — exactly the failure the per-mart uniqueness tests are meant to prevent.
-- This is the second line of defence: even if a uniqueness test is removed or a
-- new fan-out slips in, the served numbers can't diverge from Gold undetected.
--
-- Reconciles SUM(val_yearfx_usd) — the nominal-USD measure common to all four
-- production/flow marts. USD is NULL pre-1994 for PEVS/PAM, but SUM skips NULLs
-- identically on both sides, so the comparison stays exact. Relative tolerance
-- (1e-6) absorbs float64 SUM non-associativity across the two grain orders; a real
-- fan-out moves the total by whole percent.
--
-- Fails (returns a row) when |serving_total - gold_total| exceeds 1e-6 of the Gold
-- total, per source.

-- PPM is the source MOST exposed to a future crosswalk fan-out: serving_ppm_annual
-- LEFT JOINs a hand-rolled prefix-LIKE ppm_xwalk, where two ppm prefixes matching one
-- product_code would duplicate rows. Its stock rows carry NULL val_yearfx_usd, but SUM
-- skips NULLs identically on both sides (as for PEVS/PAM pre-1994), so the comparison
-- stays exact (DBT-1).
{% set pairs = [
    ('pevs',     'serving_pevs_annual',     'gold_pevs_production'),
    ('pam',      'serving_pam_annual',      'gold_pam_production'),
    ('ppm',      'serving_ppm_annual',      'gold_ppm_production'),
    ('comex',    'serving_comex_annual',    'gold_comex_flows'),
    ('comtrade', 'serving_comtrade_annual', 'gold_comtrade_flows')
] %}

with checks as (
    {% for source, mart, gold in pairs %}
    select
        '{{ source }}'                                              as source,
        (select sum(val_yearfx_usd) from {{ ref(mart) }})          as serving_total,
        (select sum(val_yearfx_usd) from {{ ref(gold) }})          as gold_total
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    source,
    serving_total,
    gold_total,
    serving_total - gold_total                              as drift,
    safe_divide(serving_total - gold_total, gold_total)     as drift_fraction
from checks
where gold_total is not null
  and abs(coalesce(serving_total, 0) - gold_total) > abs(gold_total) * 1e-6
