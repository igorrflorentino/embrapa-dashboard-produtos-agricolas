{#-
    Row-level data quality enum.
    A row is OK only when it has a quantity (in any family) and a nominal BRL
    value. `qty` is the native quantity (presence of a source reading) — NOT
    qty_base, so an unconvertible unit (family='desconhecida') still counts as
    "has a quantity"; convertibility is surfaced separately for curation.
-#}
{% macro data_quality_flag(qty, val_brl) -%}
    CASE
        WHEN {{ qty }} IS NOT NULL AND {{ val_brl }} IS NOT NULL THEN 'OK'
        WHEN {{ qty }} IS NOT NULL AND {{ val_brl }} IS NULL     THEN 'MISSING_VALUE'
        WHEN {{ qty }} IS NULL     AND {{ val_brl }} IS NOT NULL THEN 'MISSING_QUANTITY'
        ELSE 'INCOMPLETE'
    END
{%- endmacro %}
