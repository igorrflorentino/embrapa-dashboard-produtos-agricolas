{#-
    Static dimensions for the 27 Brazilian federative units. Encoded as
    CASE expressions instead of a seed because (a) they don't change and
    (b) inlining lets BigQuery push the projection through joins.
-#}
{% macro state_name(uf_col) -%}
    case {{ uf_col }}
        when 'AC' then 'Acre'
        when 'AL' then 'Alagoas'
        when 'AP' then 'Amapá'
        when 'AM' then 'Amazonas'
        when 'BA' then 'Bahia'
        when 'CE' then 'Ceará'
        when 'DF' then 'Distrito Federal'
        when 'ES' then 'Espírito Santo'
        when 'GO' then 'Goiás'
        when 'MA' then 'Maranhão'
        when 'MT' then 'Mato Grosso'
        when 'MS' then 'Mato Grosso do Sul'
        when 'MG' then 'Minas Gerais'
        when 'PA' then 'Pará'
        when 'PB' then 'Paraíba'
        when 'PR' then 'Paraná'
        when 'PE' then 'Pernambuco'
        when 'PI' then 'Piauí'
        when 'RJ' then 'Rio de Janeiro'
        when 'RN' then 'Rio Grande do Norte'
        when 'RS' then 'Rio Grande do Sul'
        when 'RO' then 'Rondônia'
        when 'RR' then 'Roraima'
        when 'SC' then 'Santa Catarina'
        when 'SP' then 'São Paulo'
        when 'SE' then 'Sergipe'
        when 'TO' then 'Tocantins'
    end
{%- endmacro %}

{% macro state_region(uf_col) -%}
    case
        when {{ uf_col }} in ('AC','AM','AP','PA','RO','RR','TO')           then 'Norte'
        when {{ uf_col }} in ('AL','BA','CE','MA','PB','PE','PI','RN','SE') then 'Nordeste'
        when {{ uf_col }} in ('DF','GO','MT','MS')                          then 'Centro-Oeste'
        when {{ uf_col }} in ('ES','MG','RJ','SP')                          then 'Sudeste'
        when {{ uf_col }} in ('PR','RS','SC')                               then 'Sul'
    end
{%- endmacro %}
