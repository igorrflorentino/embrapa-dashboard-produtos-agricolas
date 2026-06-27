-- Regression guard for the 1985 reform-boundary source correction
-- (macros/ibge_1985_cruzado_correction.sql). After the correction, the 1985 PAM/PPM median
-- DEFLATED price must sit within an order of magnitude of its 1984 + 1986 neighbours — NOT the
-- ~1000x cliff the IBGE "Mil Cruzeiros"-labelled-but-Cruzados-magnitude 1985 value caused.
--
-- Fails (returns a row) if 1985 is still < 1/10 of the neighbour average, which means the
-- correction regressed (e.g. the macro got unwired) OR IBGE re-introduced the artifact in a
-- future ingest. Uses the massa family (the dominant, always-present one for both sources).
{% set pairs = [
    ('pam', 'gold_pam_production'),
    ('ppm', 'gold_ppm_production')
] %}

with yearly as (
    {% for src, tbl in pairs %}
    select
        '{{ src }}' as src,
        reference_year,
        approx_quantiles(safe_divide(val_real_ipca_brl, qty_native), 100)[offset(50)] as med_price
    from {{ ref(tbl) }}
    where reference_year between 1984 and 1986
      and family = 'massa'
      and val_real_ipca_brl > 0
      and qty_native > 0
    group by src, reference_year
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

pivoted as (
    select
        src,
        max(if(reference_year = 1984, med_price, null)) as y1984,
        max(if(reference_year = 1985, med_price, null)) as y1985,
        max(if(reference_year = 1986, med_price, null)) as y1986
    from yearly
    group by src
)

select src, y1984, y1985, y1986
from pivoted
where y1985 is not null and y1984 is not null and y1986 is not null
  and y1985 < 0.1 * ((y1984 + y1986) / 2)
