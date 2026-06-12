-- Singular test: PAM measures must be CONSERVED across Silver→Gold.
--
-- gold_pam_production PIVOTS the variable_code dimension away: it GROUP BYs
-- (reference_year, state_acronym, city_code, product_code) and lifts each measure
-- with max(case when variable_code = ... ) — quantity (qty_base), value, área
-- plantada, área colhida. That max() assumes EXACTLY ONE row per (grain, measure)
-- — true because the natural key includes variable_code + unit_of_measure, and
-- each PAM variable has a single unit. If a second row ever appeared at a grain,
-- max() would KEEP one and DROP the other instead of summing.
--
-- This pins the assumption with a grand-total reconciliation per measure. A drift
-- means a grain silently lost a row to max(), or a fan-out / filter changed the
-- totals between layers. NULLs are skipped consistently on both sides (the Gold
-- `having ... is not null` only drops grains that contribute 0 to every SUM).
--
-- Relative tolerance 1e-6 (float64 SUM is non-associative across the two grain
-- orders); a real dropped row moves the total by whole percent.
--
-- Fails (returns a row) when |gold_total - silver_total| exceeds 1e-6 of the
-- Silver total, per measure.

with checks as (

    select
        'qty_base'                                                              as measure,
        (select sum(qty_base) from {{ ref('silver_ibge_pam') }})                as silver_total,
        (select sum(qty_base) from {{ ref('gold_pam_production') }})            as gold_total

    union all

    select
        'val_brl',
        (select sum(numeric_value) from {{ ref('silver_ibge_pam') }} where is_monetary_value),
        (select sum(val_yearfx_brl) from {{ ref('gold_pam_production') }})

    union all

    select
        'area_planted_ha',
        (select sum(numeric_value) from {{ ref('silver_ibge_pam') }}
            where variable_code = '{{ var("pam_variable_area_planted") }}'),
        (select sum(area_planted_ha) from {{ ref('gold_pam_production') }})

    union all

    select
        'area_harvested_ha',
        (select sum(numeric_value) from {{ ref('silver_ibge_pam') }}
            where variable_code = '{{ var("pam_variable_area_harvested") }}'),
        (select sum(area_harvested_ha) from {{ ref('gold_pam_production') }})

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
