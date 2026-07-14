{#-
    Convert a raw source string into FLOAT64, mapping the "no data" sentinels
    ('...', '..', '*', 'X', '') and any non-numeric junk to NULL. Brazilian
    decimal comma is normalized to '.'.

    ``dash_is_zero`` (IBGE/SIDRA only): SIDRA's '-' means "dado numérico igual a
    zero não resultante de arredondamento" — an EXACT MEASURED ZERO, semantically
    distinct from '...' = "não disponível". Pass ``dash_is_zero=true`` for IBGE
    ``valor`` columns so a published zero maps to 0.0 (not NULL); otherwise
    "production went to zero" is conflated with "not surveyed" and dropped/flagged
    as missing downstream. Non-IBGE sources (BCB/COMEX/COMTRADE) leave the default
    false → '-' stays NULL, byte-identical to before.
-#}
{% macro safe_numeric(column, dash_is_zero=false) -%}
    SAFE_CAST(
        REPLACE(
            NULLIF(
                NULLIF(
                    NULLIF(
                        NULLIF(
                            {% if dash_is_zero -%}
                            CASE WHEN TRIM({{ column }}) = '-' THEN '0'
                                 ELSE NULLIF(TRIM({{ column }}), '') END
                            {%- else -%}
                            NULLIF(NULLIF(TRIM({{ column }}), ''), '-')
                            {%- endif %},
                        '...'),
                    '..'),
                '*'),
            'X'),
        ',', '.') AS FLOAT64
    )
{%- endmacro %}
