-- Singular test: PEVS quantity + value must be CONSERVED across Silver→Gold.
--
-- gold_pevs_production PIVOTS the variable_code dimension away: it GROUP BYs
-- (reference_year, state_acronym, city_code, product_code) and lifts the single
-- quantity row and the single monetary row with max() (the quantity row carries
-- qty_base + qty_native; the monetary row carries the value). That max() assumes
-- EXACTLY ONE physical unit (and one monetary row) per grain — the model's own
-- comment flags that if a product ever reported under TWO units in the same
-- (year, state, city), max() KEEPS one and DROPS the other instead of summing.
--
-- This pins that assumption with a grand-total reconciliation. A drift means a
-- grain silently lost a row to max() (a second unit / a duplicate monetary row),
-- or a fan-out / filter changed the totals between the layers:
--   • qty_base  : Gold max(qty_base)   vs Silver SUM(qty_base)        (only the
--                 quantity rows carry it; monetary rows are NULL → skipped)
--   • val (BRL) : Gold val_yearfx_brl  vs Silver SUM(monetary value)  (val_raw =
--                 the single monetary numeric_value, already present-BRL in Silver)
--
-- The `having qty_native is not null or val_raw is not null` filter in Gold only
-- drops grains where BOTH are NULL — which contribute 0 to either SUM — so it
-- cannot move the totals. NULLs are skipped consistently on both sides.
--
-- Relative tolerance (1e-6) because float64 SUM is non-associative across the two
-- grain orders; a real dropped row moves the total by whole percent. Verified on
-- prod: both drifts are exactly 0.0.
--
-- Fails (returns a row) when |gold_total - silver_total| exceeds 1e-6 of the
-- Silver total, per measure.

with checks as (

    select
        'qty_base'                                                              as measure,
        (select sum(qty_base) from {{ ref('silver_ibge_pevs') }})               as silver_total,
        (select sum(qty_base) from {{ ref('gold_pevs_production') }})            as gold_total

    union all

    select
        'val_brl',
        (select sum(numeric_value) from {{ ref('silver_ibge_pevs') }} where is_monetary_value),
        (select sum(val_yearfx_brl) from {{ ref('gold_pevs_production') }})

)

select
    measure,
    silver_total,
    gold_total,
    gold_total - silver_total                                  as drift,
    safe_divide(gold_total - silver_total, silver_total)       as drift_fraction
from checks
where silver_total is not null
  and abs(coalesce(gold_total, 0) - silver_total) > abs(silver_total) * 1e-6
