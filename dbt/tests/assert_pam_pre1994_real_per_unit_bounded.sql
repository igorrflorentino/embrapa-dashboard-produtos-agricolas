-- Magnitude guard for the pre-1994 deflation/currency chain in gold_pam_production.
--
-- PAM rides the IDENTICAL currency-reform + IPCA/IGP-M/IGP-DI machinery as PEVS,
-- but reaches back to 1974 (vs PEVS's 1986) — the MOST hyperinflationary years
-- (1974-1985 Cruzeiro era) are PAM-exclusive. If the historical_currency_factors
-- seed is dropped, given a WRONG factor value, or the deflation chain breaks,
-- pre-1994 real per-unit values explode by ~1e6-1e9. This is the OUTCOME bound
-- (a wrong factor value still passes the coverage test but yields absurd
-- magnitudes); assert_monetary_units_have_currency_factor is the COVERAGE bound.
--
-- Per-UNIT (not total) is the cross-year-stationary quantity: real totals scale
-- with production volume and are legitimately large, but a real price per base
-- unit stays in the same order of magnitude across decades by construction.
--
-- CALIBRATION: severity is WARN (not error) because the ceiling below is inherited
-- from the PEVS guard and has NOT yet been calibrated against PAM's real maximum on
-- prod (PAM is a broader, finer-grained crop universe than PEVS). The R$1,000,000
-- ceiling is deliberately conservative — ~100-1000x below any seed-regression
-- magnitude (1e8-1e9), so it still catches the catastrophe, while high enough that
-- a legitimately pricey crop won't false-warn. After one prod run, replace the
-- ceiling with ~10x the observed MAX and promote to severity='error' (mirroring
-- assert_pre1994_real_per_unit_bounded for PEVS, which cites its prod-verified max).
--
-- Warns (returns rows) when any pre-1994 PAM row breaches the ceiling.

{{ config(severity='warn') }}

{% set ceiling = 1000000 %}

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
    from {{ ref('gold_pam_production') }}
    where reference_year < 1994
      and qty_base > 0
)

select *
from per_unit
where max_real_per_unit > {{ ceiling }}
