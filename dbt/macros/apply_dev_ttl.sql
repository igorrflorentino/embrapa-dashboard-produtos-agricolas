{#-
    Set a 7-day default table expiration on every dbt-managed schema in the dev
    target. Sandboxed dev tables otherwise accumulate forever; the TTL means an
    abandoned dev branch self-cleans within a week.

    Runs as an `on-run-end` hook so it fires after dbt has already created the
    dev_silver / dev_gold schemas; `ALTER SCHEMA` would otherwise fail on a
    first build of a fresh project.

    Intentionally a no-op in `prod` target — production datasets never expire.
-#}
{% macro apply_dev_ttl(days=7) -%}
    {% if target.name != 'dev' %}
        {{ log("apply_dev_ttl: target is " ~ target.name ~ ", skipping.", info=False) }}
    {% else %}
        {% set schemas = [
            target.schema ~ '_silver',
            target.schema ~ '_gold',
        ] %}
        {% for schema in schemas %}
            {% set sql -%}
                alter schema `{{ target.project }}`.`{{ schema }}`
                set options (default_table_expiration_days = {{ days }})
            {%- endset %}
            {% do run_query(sql) %}
            {{ log("apply_dev_ttl: " ~ schema ~ " → " ~ days ~ " days", info=True) }}
        {% endfor %}
    {% endif %}
{%- endmacro %}
