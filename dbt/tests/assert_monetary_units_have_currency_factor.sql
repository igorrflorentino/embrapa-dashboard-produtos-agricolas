-- Coverage guard for the currency-reform seed.
--
-- Every (reference_year, unit_of_measure) that carries a MONETARY value in
-- silver_ibge_pevs must find a matching currency-factor seed row. A miss means
-- the date-aware LEFT JOIN produced a NULL brl_factor → NULL numeric_value →
-- the monetary value silently vanished from every downstream analysis (it would
-- only show up as data_quality_flag = MISSING_VALUE, indistinguishable from a
-- genuinely absent IBGE value).
--
-- This catches both a seed gap (year not covered) and a unit-of-measure string
-- the seed doesn't recognize (e.g. IBGE renames a unit). Returns rows on a miss.
with monetary_units as (
    select distinct
        reference_year,
        unit_of_measure
    from {{ ref('silver_ibge_pevs') }}
    where is_monetary_value
)
select
    mu.reference_year,
    mu.unit_of_measure
from monetary_units mu
left join {{ ref('historical_currency_factors') }} fx
    on lower(trim(mu.unit_of_measure)) = lower(trim(fx.unit_of_measure))
   and mu.reference_year between fx.year_from and fx.year_to
where fx.brl_factor is null
