-- ────────────────────────────────────────────────────────────────────────────
-- dim_geo_br — conformed geography dimension for Brazil's 27 federative units.
--
-- Single source of truth for UF → name / region / region abbreviation, reused by
-- every serving mart that carries a `state_acronym`. Encoded from the static
-- `state_dimensions` macros (the 27 UFs never change) rather than SELECT DISTINCT
-- on a fact table, so the dimension is COMPLETE even for a UF absent from the
-- current data window. `region_abbrev` (N/NE/CO/SE/S) matches the frontend's
-- `ufData.region` contract (docs/frontend_data_contract.md §7.3).
--
-- Grain: one row per UF. PK = state_acronym.
-- ────────────────────────────────────────────────────────────────────────────

with ufs as (

    select uf
    from unnest([
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
        'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
        'SP', 'SE', 'TO'
    ]) as uf

),

named as (

    select
        uf                          as state_acronym,
        {{ state_name('uf') }}      as state_name,
        {{ state_region('uf') }}    as region
    from ufs

)

select
    state_acronym,
    state_name,
    region,
    case region
        when 'Norte'        then 'N'
        when 'Nordeste'     then 'NE'
        when 'Centro-Oeste' then 'CO'
        when 'Sudeste'      then 'SE'
        when 'Sul'          then 'S'
    end as region_abbrev,
    -- IBGE official macro-region codes (1=N, 2=NE, 3=SE, 4=S, 5=CO).
    case region
        when 'Norte'        then 1
        when 'Nordeste'     then 2
        when 'Sudeste'      then 3
        when 'Sul'          then 4
        when 'Centro-Oeste' then 5
    end as ibge_region_code
from named
