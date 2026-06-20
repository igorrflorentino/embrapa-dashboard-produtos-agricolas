-- Singular test: PPM measures must be CONSERVED across Silver→Gold.
--
-- gold_ppm_production PIVOTS the variable_code dimension away: it GROUP BYs
-- (reference_year, state_acronym, city_code, product_code) and lifts each measure
-- with max(...) — quantity (qty_base) and value. That max() assumes EXACTLY ONE row
-- per (grain, measure) — true because the natural key includes variable_code +
-- unit_of_measure. This assumption is HIGHER-RISK for PPM than PAM because PPM's
-- product universe spans MULTIPLE unit families (Cabeças/Mil litros/Mil dúzias/
-- Quilogramas), so a broken single-unit max() across families would silently drop a
-- quantity row.
--
-- Grand-total reconciliation per measure; a drift means a grain silently lost a row
-- to max() or a fan-out/filter changed the totals. Relative tolerance 1e-6.
--
-- Fails (returns a row) when |gold_total - silver_total| exceeds 1e-6 of the Silver
-- total, per measure.

with checks as (

    select
        'qty_base'                                                              as measure,
        (select sum(qty_base) from {{ ref('silver_ibge_ppm') }})                as silver_total,
        (select sum(qty_base) from {{ ref('gold_ppm_production') }})            as gold_total

    union all

    select
        'val_brl',
        (select sum(numeric_value) from {{ ref('silver_ibge_ppm') }} where is_monetary_value),
        (select sum(val_yearfx_brl) from {{ ref('gold_ppm_production') }})

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
