-- Agronomic sanity for PAM: planted area must be >= harvested area (you cannot harvest
-- more land than you planted). A few historical SIDRA source rows violate this — e.g.
-- 1990 Manaus (1300805) Mandioca planted=50 / harvested=650 ha, and 1993 (5210406)
-- Cana planted=790 / harvested=890 ha. These are SIDRA source errors, carried FAITHFULLY
-- rather than silently corrected (project rule: mark anomalies, never substitute).
--
-- WARN (not error): the known source violations surface in the build output without
-- hard-blocking the whole prod build, and any NEW violation is flagged for review. If the
-- surfaced set should also be visible IN-PRODUCT, promote it to a data_quality_flag tier.
--
-- Fails (returns rows) if a PAM Gold row reports area_planted_ha < area_harvested_ha.

{{ config(severity='warn') }}

select
    reference_year,
    state_acronym,
    city_code,
    product_code,
    area_planted_ha,
    area_harvested_ha
from {{ ref('gold_pam_production') }}
where area_planted_ha is not null
  and area_harvested_ha is not null
  and area_planted_ha < area_harvested_ha
