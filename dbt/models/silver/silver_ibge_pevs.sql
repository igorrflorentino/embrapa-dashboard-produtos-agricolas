{{
    config(
        materialized='table',
        partition_by={
            'field': 'reference_year',
            'data_type': 'int64',
            'range': {'start': 1970, 'end': 2050, 'interval': 1}
        },
        cluster_by=['state_acronym', 'product_code', 'variable_code']
    )
}}

with deduplicated as (

    -- Bronze is append-only; keep only the latest ingestion per natural key.
    select *
    from {{ source('bronze_ibge', 'sidra_raw') }}
    where variavel_codigo in (
              '{{ var("ibge_variable_quantity") }}',
              '{{ var("ibge_variable_value") }}'
          )
      and nivel_territorial = 'Município'
    qualify row_number() over (
        partition by ano, municipio_codigo, tipo_de_produto_extrativo_codigo, variavel_codigo, unidade_de_medida
        order by ingestion_timestamp desc
    ) = 1

),

parsed as (

    select
        cast(ano as int64)                                                          as reference_year,
        municipio_codigo                                                            as city_code,
        regexp_replace(municipio, r'\s-\s[A-Z]{2}$', '')                            as city_name,
        regexp_extract(municipio, r'\s-\s([A-Z]{2})$')                              as state_acronym,
        -- The SIDRA values endpoint exposes a display id (e.g. "1.3") in the
        -- prefix of `tipo_de_produto_extrativo`. We don't keep it — the
        -- canonical product code comes from the `ibge_product_codes` seed
        -- (e.g. "3405", the classification-193 category id from .env).
        trim(regexp_replace(tipo_de_produto_extrativo, r'^([^-]+)\s-\s', ''))       as product_description,
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
    seed.classification_code                                                        as product_code,
    p.product_description,
    p.variable_code,
    p.variable_name,
    p.unit_of_measure,

    -- Monetary values: apply the currency seed factor (which embeds both the
    -- "Mil" multiplier AND the cumulative reform divisions Cz$→...→R$). The
    -- IPCA chain index only captures inflation, NOT currency reforms — without
    -- this factor, pre-1994 values come out 10^6 to 10^9 times too large.
    -- Non-monetary (quantity) values keep the simple "x1000 if mil" path,
    -- though current PEVS units (Toneladas, Metros cúbicos) never trigger it.
    case
        when p.variable_code = '{{ var("ibge_variable_value") }}' then
            p.raw_numeric_value * fx.brl_factor
        when lower(p.unit_of_measure) like '%mil%' then
            p.raw_numeric_value * 1000.0
        else
            p.raw_numeric_value
    end as numeric_value,

    case when p.variable_code = '{{ var("ibge_variable_quantity") }}'
              and regexp_contains(lower(p.unit_of_measure), r'tonelada') then true else false end as is_quantity_tons,
    case when p.variable_code = '{{ var("ibge_variable_quantity") }}'
              and regexp_contains(lower(p.unit_of_measure), r'metro') then true else false end as is_quantity_m3,
    case when p.variable_code = '{{ var("ibge_variable_value") }}' then true else false end as is_monetary_value,

    p.ingestion_timestamp
from parsed p
left join {{ ref('ibge_product_codes') }} seed
    on p.product_description = seed.product_description
left join {{ ref('historical_currency_factors') }} fx
    on p.unit_of_measure = fx.unit_of_measure
