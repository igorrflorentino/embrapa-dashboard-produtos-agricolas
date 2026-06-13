-- Magnitude guard for the Jul-1994 currency changeover in the year-FX columns.
--
-- COMPLEMENTARY to assert_pre1994_real_per_unit_bounded: that test bounds the
-- val_real_* deflation chain for reference_year < 1994; this one pins the
-- changeover year ITSELF, which the pre-1994 guard does not cover.
--
-- PTAX (SGS 1) is CR$/US$ until 1994-06-30 (~450-2750) and R$/US$ from
-- 1994-07-01 (~0.85). The Gold fx_year CTEs therefore average ONLY the R$ half
-- for 1994; if a regression re-includes the CR$ half, the 1994 year-average
-- lands in the hundreds and val_yearfx_usd comes out ~1000x too small.
--
-- The implied year FX rate is recovered from the published columns as
-- val_yearfx_brl / val_yearfx_usd (PEVS/PAM divide BRL by the average;
-- COMTRADE multiplies USD by it — both reduce to the same ratio). For 1994 it
-- must be a plausible R$/US$ rate: the Jul-Dec 1994 PTAX average is ~0.87, so
-- [0.5, 2] is a wide no-false-positive band while any changeover-mixing
-- regression overshoots it by ~2-3 orders of magnitude.
--
-- Fails (returns rows) when any 1994 row's implied rate leaves the band.

with implied as (

    select
        'gold_pevs_production' as model,
        safe_divide(val_yearfx_brl, val_yearfx_usd) as implied_brl_per_usd
    from {{ ref('gold_pevs_production') }}
    where reference_year = 1994

    union all

    select
        'gold_pam_production',
        safe_divide(val_yearfx_brl, val_yearfx_usd)
    from {{ ref('gold_pam_production') }}
    where reference_year = 1994

    union all

    select
        'gold_comtrade_flows',
        safe_divide(val_yearfx_brl, val_yearfx_usd)
    from {{ ref('gold_comtrade_flows') }}
    where reference_year = 1994

)

select model, implied_brl_per_usd
from implied
where implied_brl_per_usd is not null
  and implied_brl_per_usd not between 0.5 and 2
