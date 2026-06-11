-- Magnitude guard for the pre-1994 deflation/currency chain (the scientific core).
--
-- The historical_currency_factors seed divides pre-reform nominal values (Mil
-- Cruzeiros, Cruzados, …) by ~1e3–1e9 to a present-BRL basis; the IPCA/IGP-M/IGP-DI
-- chain then deflates them to cross-year-comparable real BRL. If the seed is
-- dropped, given a WRONG factor value, or the deflation chain breaks, pre-1994
-- real per-unit values explode by ~1e6–1e9 (e.g. 1990 castanha-do-pará would read
-- ~R$4.9e8 per tonne instead of ~R$478).
--
-- This is COMPLEMENTARY to assert_monetary_units_have_currency_factor: that test
-- guards seed COVERAGE (a missing (year, unit) row); this guards the numeric
-- OUTCOME — a wrong factor value or a broken chain still passes the coverage test
-- but produces matched-but-absurd magnitudes, which only an outcome bound catches.
--
-- Per-UNIT (not total) is the cross-year-stationary quantity: real totals scale
-- with production volume and are legitimately large, but a real price per base
-- unit stays in the same order of magnitude across decades by construction.
--
-- Verified on prod (2026-06): 22 420 pre-1994 monetary rows, MAX real per-unit
-- R$8 945, median R$114. The R$100 000 ceiling is ~11x the observed max (no false
-- positive) and ~1000x below any seed-regression magnitude. All three deflators
-- are checked (a seed fault hits them together; a per-index bug hits only one).
--
-- Fails (returns rows) when any pre-1994 row breaches the ceiling.

{% set ceiling = 100000 %}

with per_unit as (
    select
        reference_year,
        product_code,
        state_acronym,
        qty_base,
        val_real_ipca_brl,
        val_real_igpm_brl,
        val_real_igpdi_brl,
        greatest(
            coalesce(safe_divide(val_real_ipca_brl,  nullif(qty_base, 0)), 0),
            coalesce(safe_divide(val_real_igpm_brl,  nullif(qty_base, 0)), 0),
            coalesce(safe_divide(val_real_igpdi_brl, nullif(qty_base, 0)), 0)
        ) as max_real_per_unit
    from {{ ref('gold_pevs_production') }}
    where reference_year < 1994
      and qty_base > 0
)

select *
from per_unit
where max_real_per_unit > {{ ceiling }}
