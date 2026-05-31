{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1960, 'end': 2050, 'interval': 1}
        },
        cluster_by=['flow', 'cmd_code', 'reporter_code', 'partner_code']
    )
}}

{#-
    UN Comtrade annual reporter→partner flows, cleaned, typed, deduplicated to the
    canonical bilateral grain — one row per (flow, year, reporter, partner, cmd).

    Filters vs the verbatim Bronze:
      • partner_code = '0' (World) is DROPPED — it is the reporter's
        pre-aggregated total over all partners and would double-count any
        SUM over partners. The total is recoverable at query time as
        GROUP BY reporter (the medallion principle: no pre-aggregated rows).
      • flowCode is normalised to a readable `flow`: X→export, M→import,
        RX→re-export, RM→re-import — the four primary regimes the frontend's
        `flow` filter exposes. Other regimes (DX/FM/MIP/…) are not requested.
      • only HS6 rows are kept (length(cmdCode)=6): the ingest requests the
        6-digit leaves of the scope chapters, so any legacy HS4 aggregate row
        (0801/44) is excluded — keeping both would double-count in Gold.
      • KEEP ONLY THE FULLY-AGGREGATED RECORD (motCode=0, customsCode=C00,
        partner2Code=0, mosCode=0). The keyed API returns, per
        (reporter,partner,cmd,flow), one aggregate row PLUS breakdown rows by
        transport mode / customs procedure / second partner; the aggregate value
        equals the sum of its breakdowns. Summing all of them (the old behaviour)
        double-counted ~2.5×. Every group has exactly one aggregate row, so this
        filter is LOSSLESS and collapses the grain to one row per
        (reporter,partner,cmd,flow,year). If a future mode-of-transport / customs
        analysis is wanted, read the verbatim breakdowns from Bronze.

    Quantity sentinels: chapter-44 rows routinely report qty = netWgt = '0.0'
    (quantity not collected). 0 is mapped to NULL so it reads as "no reading"
    (→ qty_base NULL, data_quality_flag MISSING_QUANTITY) rather than a real zero.

    Stays materialized=table: the filtered scope (HS 0801 + chapter 44, all
    reporters × partners, annual) is small. Revisit with insert_overwrite if a
    full historical backfill over decades makes the rebuild costly.
-#}

with deduplicated as (

    select *
    from {{ source('bronze_comtrade', 'comtrade_flows_raw') }}
    where partnerCode != '0'                       -- drop the World aggregate
      and flowCode in ('X', 'M', 'RX', 'RM')       -- four primary regimes
      and length(cmdCode) = 6                       -- HS6 only (exclude legacy HS4)
      and motCode = '0'                             -- ┐ keep only the fully-
      and customsCode = 'C00'                       -- │ aggregated record; the
      and partner2Code = '0'                        -- │ breakdowns sum INTO it,
      and mosCode = '0'                             -- ┘ so don't re-sum them
    qualify row_number() over (
        partition by
            refYear, reporterCode, partnerCode, partner2Code,
            cmdCode, flowCode, customsCode, mosCode, motCode, qtyUnitCode
        order by ingestion_timestamp desc
    ) = 1

),

parsed as (

    select
        case flowCode
            when 'X'  then 'export'
            when 'M'  then 'import'
            when 'RX' then 're-export'
            when 'RM' then 're-import'
        end                                                 as flow,
        cast(refYear as int64)                              as reference_year,
        reporterCode                                        as reporter_code,
        partnerCode                                         as partner_code,
        partner2Code                                        as partner2_code,
        cmdCode                                             as cmd_code,
        substr(cmdCode, 1, 2)                               as hs_chapter,
        customsCode                                         as customs_code,
        mosCode                                             as mode_of_supply_code,
        motCode                                             as mode_of_transport_code,
        qtyUnitCode                                         as qty_unit_code,
        -- 0.0 sentinel ('quantity not collected') → NULL, not a real zero.
        nullif({{ safe_numeric('qty') }},     0)            as qty_native_raw,
        nullif({{ safe_numeric('netWgt') }},  0)            as net_weight_kg,
        nullif({{ safe_numeric('grossWgt') }}, 0)           as gross_weight_kg,
        -- primaryValue is the headline trade value (US$): FOB for exports,
        -- CIF for imports. cif/fob are kept where the reporter splits them out.
        {{ safe_numeric('primaryValue') }}                  as primary_value_usd,
        {{ safe_numeric('cifvalue') }}                      as cif_value_usd,
        {{ safe_numeric('fobvalue') }}                      as fob_value_usd,
        ingestion_timestamp
    from deduplicated

)

-- Physical-unit family for the reported quantity. comtrade_unit maps the
-- numeric qty_unit_code → a canonical unit label (unit_raw); unit_family_conversions
-- turns that into family / base_unit / to_base. Units outside the 5 families
-- (e.g. length in metres, packages) fall to 'desconhecida' with NULL qty_base —
-- never an invented conversion. net_weight_kg is always kilograms (massa), the
-- measure comparable across HS codes, and is summed directly in Gold.
select
    p.flow,
    p.reference_year,
    p.reporter_code,
    p.partner_code,
    p.partner2_code,
    p.cmd_code,
    p.hs_chapter,
    p.customs_code,
    p.mode_of_supply_code,
    p.mode_of_transport_code,
    p.qty_unit_code,
    u.unit_name                                             as unit_native,
    u.unit_symbol                                           as unit_native_symbol,
    coalesce(ufc.family, 'desconhecida')                    as family,
    ufc.base_unit                                           as base_unit,
    p.qty_native_raw                                        as qty_native,
    p.qty_native_raw * ufc.to_base                          as qty_base,
    p.net_weight_kg,
    p.gross_weight_kg,
    p.primary_value_usd,
    p.cif_value_usd,
    p.fob_value_usd,
    p.ingestion_timestamp
from parsed p
left join {{ ref('comtrade_unit') }} u
    on p.qty_unit_code = u.qty_unit_code
left join {{ ref('unit_family_conversions') }} ufc
    on nullif(u.unit_raw, '') = ufc.unit_raw
where p.flow is not null
