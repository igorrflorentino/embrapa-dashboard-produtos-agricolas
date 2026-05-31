{{
    config(
        materialized='table',
        partition_by={'field': 'reference_date', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['flow', 'ncm_code', 'country_code', 'state_acronym']
    )
}}

{#-
    Stays materialized=table for now. The filtered scope (castanha NCMs + HS
    chapter 44) across month×NCM×country×UF×route is small enough that a full
    rebuild is cheap; revisit with an insert_overwrite incremental (like
    silver_ibge_pevs, partitioned on reference_date) if the chapter-44 volume
    over decades makes the rebuild costly.

    Grain: the FULL source grain — one row per
    (flow, year, month, NCM, country, UF, transport route, customs office,
    statistical unit). Gold aggregates this up to month×NCM×country×UF. We keep
    the source grain in Silver so no detail is lost and the dedupe key matches
    a single Bronze row exactly (Bronze is append-only; delta re-ingests the
    running year, so the same source row reappears with a newer
    ingestion_timestamp — qualify keeps the latest).
-#}

with deduplicated as (

    select *
    from {{ source('bronze_comex', 'comex_flows_raw') }}
    qualify row_number() over (
        partition by
            flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM, CO_VIA, CO_URF, CO_UNID
        order by ingestion_timestamp desc
    ) = 1

),

parsed as (

    select
        flow,
        cast(CO_ANO as int64)                               as reference_year,
        cast(CO_MES as int64)                               as reference_month,
        date(cast(CO_ANO as int64), cast(CO_MES as int64), 1) as reference_date,
        CO_NCM                                              as ncm_code,
        substr(CO_NCM, 1, 2)                                as hs_chapter,
        CO_PAIS                                             as country_code,
        SG_UF_NCM                                           as state_acronym,
        CO_VIA                                              as transport_route_code,
        CO_URF                                              as customs_office_code,
        CO_UNID                                             as stat_unit_code,
        {{ safe_numeric('QT_ESTAT') }}                      as statistical_quantity,
        {{ safe_numeric('KG_LIQUIDO') }}                    as net_weight_kg,
        -- VL_FOB / VL_FRETE / VL_SEGURO are nominal US$ FOB at the month of
        -- record. VL_FRETE / VL_SEGURO are import-only (NULL for export rows).
        {{ safe_numeric('VL_FOB') }}                        as val_fob_usd,
        {{ safe_numeric('VL_FRETE') }}                      as freight_usd,
        {{ safe_numeric('VL_SEGURO') }}                     as insurance_usd,
        ingestion_timestamp
    from deduplicated

)

-- Physical-unit family for statistical_quantity. The NCM statistical unit
-- (comex_unit) is the source label (unit_native); family / base_unit / to_base
-- come from the unit-family seeds (per-product crosswalk overrides the generic
-- table). Units outside the 5 families (e.g. METRO linear, BILHOES DE UI) fall
-- to 'desconhecida' with a NULL qty_base — never an invented conversion.
-- net_weight_kg is left untouched: it is always kilograms (massa), the only
-- quantity comparable across NCMs, and is summed directly in Gold.
select
    p.flow,
    p.reference_year,
    p.reference_month,
    p.reference_date,
    p.ncm_code,
    p.hs_chapter,
    p.country_code,
    p.state_acronym,
    p.transport_route_code,
    p.customs_office_code,
    p.stat_unit_code,
    u.unit_name                                             as unit_native,
    u.unit_symbol                                           as unit_native_symbol,
    coalesce(ufp.family, ufc.family, 'desconhecida')        as family,
    coalesce(ufp.base_unit, ufc.base_unit)                  as base_unit,
    p.statistical_quantity                                  as qty_native,
    p.statistical_quantity * coalesce(ufp.to_base, ufc.to_base) as qty_base,
    p.net_weight_kg,
    p.val_fob_usd,
    p.freight_usd,
    p.insurance_usd,
    p.ingestion_timestamp
from parsed p
left join {{ ref('comex_unit') }} u
    on p.stat_unit_code = u.co_unid
left join {{ ref('unit_family_conversions') }} ufc
    on lower(trim(u.unit_name)) = ufc.unit_raw
left join {{ ref('product_unit_factors') }} ufp
    on ufp.source = 'comex'
    and ufp.product_code = p.ncm_code
    and lower(trim(u.unit_name)) = ufp.unit_raw
where p.reference_date is not null
