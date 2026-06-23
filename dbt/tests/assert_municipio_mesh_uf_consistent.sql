-- dim_geo_municipio (built from the IBGE localidades mesh seed) carries each
-- município's UF + grande região; dim_geo_br (built from the static state_dimensions
-- macro) is the conformed UF→region source of truth. They are INDEPENDENT encodings
-- of the same IBGE mapping, so this guards silent DRIFT between the mesh seed and the
-- macro (e.g. a seed refresh that disagrees with the macro). Returns the mismatching
-- UFs; 0 rows = consistent. Cheap (27 UFs × the small dims).
select
    m.state_acronym,
    m.region_abbrev as mesh_region,
    b.region_abbrev as dim_geo_br_region
from {{ ref('dim_geo_municipio') }} m
join {{ ref('dim_geo_br') }} b
    on b.state_acronym = m.state_acronym
where m.region_abbrev != b.region_abbrev
group by 1, 2, 3
