{#-
    Row-level data quality enum.
    A row is OK only when it has both a quantity (in any unit) and a nominal BRL value.
-#}
{% macro data_quality_flag(qty_tons, qty_m3, val_brl) -%}
    CASE
        WHEN ({{ qty_tons }} IS NOT NULL OR {{ qty_m3 }} IS NOT NULL)
             AND {{ val_brl }} IS NOT NULL
            THEN 'OK'
        WHEN ({{ qty_tons }} IS NOT NULL OR {{ qty_m3 }} IS NOT NULL)
             AND {{ val_brl }} IS NULL
            THEN 'MISSING_VALUE'
        WHEN ({{ qty_tons }} IS NULL AND {{ qty_m3 }} IS NULL)
             AND {{ val_brl }} IS NOT NULL
            THEN 'MISSING_QUANTITY'
        ELSE 'INCOMPLETE'
    END
{%- endmacro %}
