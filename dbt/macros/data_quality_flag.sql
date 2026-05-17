{#-
    Row-level data quality enum.
    A row is OK only when it has both a quantity (in any unit) and a nominal BRL value.
-#}
{% macro data_quality_flag(qty_kg, qty_tons, qty_m3, qty_liters, val_brl) -%}
    CASE
        WHEN ({{ qty_kg }} IS NOT NULL
              OR {{ qty_tons }} IS NOT NULL
              OR {{ qty_m3 }} IS NOT NULL
              OR {{ qty_liters }} IS NOT NULL)
             AND {{ val_brl }} IS NOT NULL
            THEN 'OK'
        WHEN ({{ qty_kg }} IS NOT NULL
              OR {{ qty_tons }} IS NOT NULL
              OR {{ qty_m3 }} IS NOT NULL
              OR {{ qty_liters }} IS NOT NULL)
             AND {{ val_brl }} IS NULL
            THEN 'MISSING_VALUE'
        WHEN ({{ qty_kg }} IS NULL
              AND {{ qty_tons }} IS NULL
              AND {{ qty_m3 }} IS NULL
              AND {{ qty_liters }} IS NULL)
             AND {{ val_brl }} IS NOT NULL
            THEN 'MISSING_QUANTITY'
        ELSE 'INCOMPLETE'
    END
{%- endmacro %}
