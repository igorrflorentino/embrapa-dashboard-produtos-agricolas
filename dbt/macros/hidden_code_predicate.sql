{#-
    hidden_code_predicate — the Ciclo de Vida visibility gate (F7), as a SQL predicate.

    Returns a NOT EXISTS clause that EXCLUDES any Gold row whose code equals a hidden
    commodity's code (dim_commodity_visibility). Drop it into the WHERE of any model
    that enumerates commodities for a RESEARCHER (the serving marts, the quality union).
    A code with no hidden-prefix row passes (visible) — so this is a no-op when nothing
    is hidden. The Python gateway's direct-Gold readers use the equivalent
    serving/sql.visibility_clause() against the SAME view (one source of truth).

    Args:
      source_literal — the short source token of THIS model's Gold table
                       (pevs | pam | ppm | comex | comtrade), matched against
                       dim_commodity_visibility.source.
      code_column    — the product/NCM/HS code column in this model.
-#}
{% macro hidden_code_predicate(source_literal, code_column) -%}
    not exists (
        select 1 from {{ ref('dim_commodity_visibility') }} v
        where v.source = '{{ source_literal }}'
          and {{ code_column }} = v.code
    )
{%- endmacro %}
