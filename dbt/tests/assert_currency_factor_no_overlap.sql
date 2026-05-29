-- Fan-out guard for the currency-reform seed.
--
-- silver_ibge_pevs converts monetary values via a date-aware LEFT JOIN:
--   on lower(unit_of_measure) = lower(fx.unit_of_measure)
--   and reference_year between fx.year_from and fx.year_to
-- If two seed rows for the SAME unit_of_measure had overlapping year ranges,
-- that join would match twice and DUPLICATE every PEVS row for those years —
-- silent double-counting that the Gold GROUP BY max() would partially mask.
--
-- This test fails (returns rows) if any such overlap exists. The seed is
-- correct today (ranges tile 1942-2099 with no overlap); this pins the
-- invariant so a future seed edit can't reintroduce the fan-out.
select
    a.unit_of_measure,
    a.year_from as a_year_from,
    a.year_to   as a_year_to,
    b.year_from as b_year_from,
    b.year_to   as b_year_to
from {{ ref('historical_currency_factors') }} a
join {{ ref('historical_currency_factors') }} b
    on lower(trim(a.unit_of_measure)) = lower(trim(b.unit_of_measure))
   and a.year_from < b.year_from        -- ordered, distinct pairs (no self-match)
   and a.year_to >= b.year_from         -- a's range reaches into b's start → overlap
