{#-
    Convert a raw IBGE/BCB string into FLOAT64, mapping placeholder sentinels
    ('-', '...', '..', '*', 'X', '') and any non-numeric junk to NULL.
    Brazilian decimal comma is normalized to '.'.
-#}
{% macro safe_numeric(column) -%}
    SAFE_CAST(
        REPLACE(
            NULLIF(
                NULLIF(
                    NULLIF(
                        NULLIF(
                            NULLIF(
                                NULLIF(TRIM({{ column }}), ''),
                            '-'),
                        '...'),
                    '..'),
                '*'),
            'X'),
        ',', '.') AS FLOAT64
    )
{%- endmacro %}
