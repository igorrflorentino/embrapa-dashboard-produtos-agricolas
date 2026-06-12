{{
    config(
        materialized='incremental',
        incremental_strategy='insert_overwrite',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['state_acronym', 'product_code', 'variable_code'],
        on_schema_change='append_new_columns'
    )
}}

{#-
    Silver for IBGE PAM (Produção Agrícola Municipal, SIDRA 5457).

    Same incremental + dedupe shape as silver_ibge_pevs (insert_overwrite by
    reference_year; keep the latest ingestion per natural key), but for PAM's five
    measures (área plantada, área colhida, quantidade, rendimento, valor). LONG
    format — one row per (year, city, product, variable); gold_pam_production
    pivots it into measure columns.

    LEAN-WINDOW ASSUMPTION: the monetary variable (215) is scaled to nominal Reais
    by ×1000 (SIDRA reports it in "Mil Reais") — valid ONLY because the configured
    window is post-1994 (PAM_START_YEAR default 2010), where the unit is always
    "Mil Reais". If PAM is ever backfilled below 1994, var 215 switches to Mil
    Cruzeiros/Cruzados/etc. and a date-aware historical_currency_factors join (as
    in silver_ibge_pevs) MUST be added — otherwise pre-1994 values come out
    10^6–10^9× too large. A dbt test guards the window (see _silver.yml).
-#}

{% set var_quantity = var("pam_variable_quantity") %}
{% set var_value = var("pam_variable_value") %}
{% set kept_variables = [
    var("pam_variable_area_planted"),
    var("pam_variable_area_harvested"),
    var_quantity,
    var("pam_variable_yield"),
    var_value,
] %}

{% if is_incremental() %}
with affected_years as (

    -- `>=` (not `>`): re-scan the boundary year so a clock-identical double load
    -- isn't skipped forever; insert_overwrite makes re-processing a year idempotent.
    select distinct ano
    from {{ source('bronze_pam', 'sidra_raw') }}
    where ingestion_timestamp >= (select coalesce(max(ingestion_timestamp), timestamp '1970-01-01') from {{ this }})

),

deduplicated as (

    select b.*
    from {{ source('bronze_pam', 'sidra_raw') }} b
    inner join affected_years ay on b.ano = ay.ano
    where b.variavel_codigo in ({{ "'" ~ kept_variables | join("','") ~ "'" }})
      and b.nivel_territorial = 'Município'
    qualify row_number() over (
        partition by b.ano, b.municipio_codigo, b.produto_das_lavouras_temporarias_e_permanentes_codigo, b.variavel_codigo, b.unidade_de_medida
        order by b.ingestion_timestamp desc
    ) = 1

),
{% else %}
with deduplicated as (

    -- Bronze is append-only; keep only the latest ingestion per natural key.
    select *
    from {{ source('bronze_pam', 'sidra_raw') }}
    where variavel_codigo in ({{ "'" ~ kept_variables | join("','") ~ "'" }})
      and nivel_territorial = 'Município'
    qualify row_number() over (
        partition by ano, municipio_codigo, produto_das_lavouras_temporarias_e_permanentes_codigo, variavel_codigo, unidade_de_medida
        order by ingestion_timestamp desc
    ) = 1

),
{% endif %}

parsed as (

    select
        cast(ano as int64)                                                          as reference_year,
        municipio_codigo                                                            as city_code,
        regexp_replace(municipio, r'\s-\s[A-Z]{2}$', '')                            as city_name,
        regexp_extract(municipio, r'\s-\s([A-Z]{2})$')                              as state_acronym,
        produto_das_lavouras_temporarias_e_permanentes_codigo                       as product_code,
        trim(produto_das_lavouras_temporarias_e_permanentes)                        as product_description,
        variavel_codigo                                                             as variable_code,
        variavel                                                                    as variable_name,
        unidade_de_medida                                                           as unit_of_measure,
        {{ safe_numeric('valor') }}                                                 as raw_numeric_value,
        ingestion_timestamp
    from deduplicated

)

select
    p.reference_year,
    p.city_code,
    p.city_name,
    p.state_acronym,
    p.product_code,
    p.product_description,
    p.variable_code,
    p.variable_name,
    p.unit_of_measure,

    -- Monetary value (var 215): SIDRA reports "Mil Reais" → ×1000 to nominal R$.
    -- No reform factor: the configured window is post-1994 (see header). Every
    -- other variable (area ha, quantity t, yield kg/ha) passes through unscaled.
    case
        when p.variable_code = '{{ var_value }}' then p.raw_numeric_value * 1000
        else p.raw_numeric_value
    end as numeric_value,

    case when p.variable_code = '{{ var_value }}' then true else false end as is_monetary_value,

    -- ── Physical-unit family (quantity rows only, var 214) ───────────────────
    -- Mirrors silver_ibge_pevs: unit_native is the source label; family/base_unit
    -- /to_base come from the generic unit-family seed (PAM has no per-product unit
    -- overrides). For the lean crop set the unit is always 'Toneladas' → massa/t.
    case when p.variable_code = '{{ var_quantity }}'
        then p.unit_of_measure end                          as unit_native,
    case when p.variable_code = '{{ var_quantity }}'
        then coalesce(ufc.family, 'desconhecida') end       as family,
    case when p.variable_code = '{{ var_quantity }}'
        then ufc.base_unit end                              as base_unit,
    case when p.variable_code = '{{ var_quantity }}'
        then p.raw_numeric_value end                        as qty_native,
    case when p.variable_code = '{{ var_quantity }}'
        then p.raw_numeric_value * ufc.to_base end          as qty_base,

    p.ingestion_timestamp
from parsed p
left join {{ ref('unit_family_conversions') }} ufc
    on lower(trim(p.unit_of_measure)) = ufc.unit_raw
