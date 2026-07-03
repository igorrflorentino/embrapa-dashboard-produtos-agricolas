-- Singular test: the value total must be CONSERVED across Gold→serving.
--
-- Each serving_*_annual mart rolls its Gold fact up to a coarser grain with plain
-- SUM(...) and then LEFT JOINs the conformed dims (dim_geo_br) + the
-- gold_produto_agrupamento. A clean roll-up + 1:1 joins must leave the grand total
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
-- serving_comex_seasonality is also a value rollup of gold_comex_flows (it just keeps
-- reference_month + a 1:1 dim_date LEFT JOIN, which dim_date.date_month's unique test
-- keeps fan-out-free), so reconcile it too — making the conservation guarantee explicit
-- rather than delegated solely to the dim_date + grain-uniqueness tests (DBT-6).
-- F7 visibility-gate SYMMETRY (added 2026-06-27). Each serving mart applies
-- hidden_code_predicate, so a commodity marked "indisponível" (dim_produto_visibility)
-- drops from the mart. The Gold side of this reconciliation MUST apply the SAME gate, or the
-- test would FALSE-FAIL the daily prod build the instant a researcher hides anything (serving
-- drops those rows while un-gated Gold keeps them, inflating drift past 1e-6). Both sides now
-- exclude identically, so conservation stays exact under hiding. The (source_token, code_column)
-- per pair mirror each mart's own hidden_code_predicate call; while dim_produto_visibility is
-- empty the predicate is a no-op and the totals are unchanged.
{% set pairs = [
    ('pevs',              'serving_pevs_annual',       'gold_pevs_production',  'pevs',     'product_code'),
    ('pam',               'serving_pam_annual',        'gold_pam_production',   'pam',      'product_code'),
    ('ppm',               'serving_ppm_annual',        'gold_ppm_production',   'ppm',      'product_code'),
    ('comex',             'serving_comex_annual',      'gold_comex_flows',      'comex',    'ncm_code'),
    ('comex_seasonality', 'serving_comex_seasonality', 'gold_comex_flows',      'comex',    'ncm_code'),
    ('comtrade',          'serving_comtrade_annual',   'gold_comtrade_flows',   'comtrade', 'cmd_code')
] %}

with checks as (
    {% for source, mart, gold, vis_token, code_col in pairs %}
    select
        '{{ source }}'                                              as source,
        (select sum(val_yearfx_usd) from {{ ref(mart) }})          as serving_total,
        (select sum(val_yearfx_usd) from {{ ref(gold) }}
         where {{ hidden_code_predicate(vis_token, code_col) }})   as gold_total
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
