-- Coverage guard for the currency-reform seed (PEVS + PAM).
--
-- Every (reference_year, unit_of_measure) that carries a MONETARY value in a SIDRA
-- Silver model must find a matching currency-factor seed row. A miss means the
-- date-aware LEFT JOIN produced a NULL brl_factor → NULL numeric_value → the
-- monetary value silently vanished from every downstream analysis (it would only
-- surface as data_quality_flag = MISSING_VALUE, indistinguishable from a genuinely
-- absent IBGE value).
--
-- Covers BOTH silver_ibge_pevs (monetary back to 1986) AND silver_ibge_pam
-- (monetary back to 1974 — deeper into the reform era, so MORE exposed to a seed
-- gap). PAM rides the exact same date-aware seed join as PEVS, so this single
-- guard keeps both honest. Catches a seed gap (year not covered) and an
-- unrecognized unit-of-measure string (e.g. IBGE renames a unit). Returns rows on
-- a miss; the `source` column identifies which model.
with monetary_units as (
    select distinct
        'pevs' as source,
        reference_year,
        unit_of_measure
    from {{ ref('silver_ibge_pevs') }}
    where is_monetary_value

    union all

    select distinct
        'pam' as source,
        reference_year,
        unit_of_measure
    from {{ ref('silver_ibge_pam') }}
    where is_monetary_value
)
select
    mu.source,
    mu.reference_year,
    mu.unit_of_measure
from monetary_units mu
left join {{ ref('historical_currency_factors') }} fx
    on lower(trim(mu.unit_of_measure)) = lower(trim(fx.unit_of_measure))
   and mu.reference_year between fx.year_from and fx.year_to
where fx.brl_factor is null
