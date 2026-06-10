"""Glossário — terms, codes, and columns for the active banco."""

from __future__ import annotations

from dash import html

from ..components.cards import card, section_header
from ..registries import banco_by_id, filter_schema_for

# Monetary-convention terms shared by every banco (the Gold column conventions).
_CONVENTIONS = [
    (
        "val_yearfx_*",
        "Valor nominal convertido pela taxa de câmbio média do ano/mês — "
        "compara magnitudes na moeda corrente da época.",
    ),
    (
        "val_real_ipca_*",
        "Valor real deflacionado pelo IPCA (IBGE) — use para comparação "
        "entre anos: remove a inflação.",
    ),
    (
        "val_real_igpm_* / val_real_igpdi_*",
        "Valores reais deflacionados por IGP-M / IGP-DI "
        "(FGV) — convenções alternativas de correção.",
    ),
    (
        "data_quality_flag",
        "Bandeira de qualidade por linha (OK, valor/quantidade ausente, "
        "incompleto) — diagnostica integridade da Gold.",
    ),
]


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    schema = filter_schema_for(banco_id)
    dim_rows = [
        html.Div(
            [html.Code(d["column"]), html.P(d.get("hint", ""), className="caption")],
            className="gloss-row",
        )
        for d in schema.get("dims", [])
    ]
    conv_rows = [
        html.Div([html.Code(code), html.P(desc, className="caption")], className="gloss-row")
        for code, desc in _CONVENTIONS
    ]
    return [
        card(
            [
                section_header(
                    f"Glossário · {banco.short}",
                    "Colunas e dimensões filtráveis",
                    action=html.Span(html.Code(banco.table), className="caption"),
                ),
                html.Div(dim_rows, className="gloss-list"),
            ]
        ),
        card(
            [
                section_header("Convenções monetárias do Gold", "Como os valores são expressos"),
                html.Div(conv_rows, className="gloss-list"),
            ]
        ),
    ]
