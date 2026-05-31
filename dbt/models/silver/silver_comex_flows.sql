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

select *
from parsed
where reference_date is not null
