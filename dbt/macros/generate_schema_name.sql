{#
  Schema naming strategy:
    dev  → <target.schema>_<custom_schema>   e.g. dbt_dev_silver, dbt_dev_gold
    prod → <custom_schema>                   e.g. silver, gold

  This means `dbt build --target prod` writes to the real Silver/Gold datasets
  without any prefix, while the default dev target stays sandboxed.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ default_schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
