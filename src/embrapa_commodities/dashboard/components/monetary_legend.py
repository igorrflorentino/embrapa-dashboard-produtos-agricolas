"""'Convenções monetárias' explainer card — how to read the val_* columns."""

from __future__ import annotations

from dash import html

from embrapa_commodities.dashboard.components.section_header import section_header


def monetary_legend() -> html.Div:
    return html.Div(
        className="card subtle",
        children=[
            section_header(
                overline="Convenções monetárias",
                title="Como ler os valores no Gold",
            ),
            html.Div(
                className="conv-grid",
                children=[
                    html.Div(
                        className="conv",
                        children=[
                            html.Div(
                                "val_real_ipca_*",
                                className="conv-tag",
                                style={
                                    "background": "rgba(29,77,126,0.10)",
                                    "color": "var(--pres-yale-blue)",
                                },
                            ),
                            html.P(
                                [
                                    "Valor projetado para hoje pela cadeia IPCA — usar para ",
                                    html.Strong("comparações entre anos"),
                                    ". Padrão deste dashboard.",
                                ]
                            ),
                        ],
                    ),
                    html.Div(
                        className="conv",
                        children=[
                            html.Div(
                                "val_real_igpm_*",
                                className="conv-tag",
                                style={
                                    "background": "rgba(0,111,53,0.10)",
                                    "color": "var(--embrapa-green-darker)",
                                },
                            ),
                            html.P(
                                "Idem, usando IGP-M como índice. Alternativa "
                                "institucional ao IPCA; maior aderência a séries de commodities."
                            ),
                        ],
                    ),
                    html.Div(
                        className="conv",
                        children=[
                            html.Div(
                                "val_yearfx_*",
                                className="conv-tag",
                                style={
                                    "background": "rgba(102,102,102,0.10)",
                                    "color": "var(--fg-2)",
                                },
                            ),
                            html.P(
                                [
                                    "Valor em R$ correntes convertido pelo câmbio médio do ano. ",
                                    html.Strong("Auditoria histórica apenas"),
                                    " — não compare entre anos.",
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
