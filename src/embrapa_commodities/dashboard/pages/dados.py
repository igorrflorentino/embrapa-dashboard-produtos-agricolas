"""/dados — Sobre os dados."""

from __future__ import annotations

from dash import dash_table, html

from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore
from embrapa_commodities.dashboard.formatting import fmt_number

PREFIX = "dados"


def layout(store: GoldStore) -> html.Div:
    lo, hi = store.year_range()
    products = store.products()
    states = store.states()
    quality = store.quality_summary()

    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=[
                    html.Div(
                        children=[
                            html.Div("Referência", className="overline"),
                            html.H1("Sobre os dados", className="page-title"),
                            html.P(
                                "Origem, cobertura, granularidade e cadência de "
                                "atualização das séries que alimentam o dashboard.",
                                className="page-sub",
                            ),
                        ]
                    ),
                    html.Div(
                        className="hero-meta",
                        children=[
                            _meta_row("Período coberto", f"{lo}–{hi}"),
                            _meta_row(
                                "Produtos rastreados",
                                fmt_number(len(products)),
                            ),
                            _meta_row(
                                "UFs com dados",
                                fmt_number(len(states)),
                            ),
                            _meta_row(
                                "Linhas no Gold",
                                fmt_number(quality["rows_total"]),
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Produção extrativa vegetal",
                        title="IBGE PEVS · tabela SIDRA 289",
                    ),
                    html.P(
                        [
                            html.Strong("O que é: "),
                            "a Pesquisa da Extração Vegetal e da Silvicultura "
                            "(PEVS) é um levantamento anual conduzido pelo "
                            "IBGE desde 1986 que mensura, por município, a "
                            "quantidade produzida e o valor da produção dos "
                            "produtos do extrativismo vegetal (alimentos, "
                            "borrachas, ceras, fibras, madeiras e oleaginosas) "
                            "e da silvicultura.",
                        ],
                        className="page-sub",
                    ),
                    html.P(
                        [
                            html.Strong("Granularidade: "),
                            "uma linha por (ano, município, produto). O Gold "
                            "deduplica e pivoteia quantidades e valor monetário "
                            "em colunas distintas.",
                        ],
                        className="page-sub",
                        style={"marginTop": "10px"},
                    ),
                    html.P(
                        [
                            html.Strong("Cadência: "),
                            "publicada anualmente, geralmente entre setembro e "
                            "outubro do ano seguinte ao de referência (dados de "
                            "2024 saem em ~set/2025).",
                        ],
                        className="page-sub",
                        style={"marginTop": "10px"},
                    ),
                    html.P(
                        [
                            html.Strong("Acesso direto: "),
                            html.A(
                                "sidra.ibge.gov.br/tabela/289",
                                href="https://sidra.ibge.gov.br/tabela/289",
                                target="_blank",
                            ),
                            ". A ingestão usa a API REST do SIDRA, dividindo "
                            "janelas de ano em chunks para respeitar o limite "
                            "de células por requisição.",
                        ],
                        className="page-sub",
                        style={"marginTop": "10px"},
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Inflação e câmbio",
                        title="BCB SGS · séries macroeconômicas",
                    ),
                    html.P(
                        "O dashboard combina os dados físicos do IBGE com séries "
                        "monetárias oficiais do Banco Central do Brasil para "
                        "permitir comparações entre anos:",
                        className="page-sub",
                    ),
                    _bcb_series_table(),
                    html.P(
                        [
                            "A cadeia mensal de inflação é construída no Silver via ",
                            html.Code("exp(sum(log(1 + pct/100)))", className="mono"),
                            ", produzindo um índice base 100 que o Gold usa "
                            "para projetar valores históricos para a base atual.",
                        ],
                        className="page-sub",
                        style={"marginTop": "10px"},
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Reformas monetárias",
                        title="Por que valores antigos não precisam de divisão manual",
                    ),
                    html.P(
                        [
                            "A nomenclatura monetária do Brasil mudou várias vezes "
                            "ao longo da série (Cz$ 1986–1989 → NCz$ 1989–1990 → "
                            "Cr$ 1990–1993 → CR$ 1993–1994 → R$ 1994–hoje), e o "
                            "IBGE publicou cada ano na moeda vigente. O Silver "
                            "aplica um seed ",
                            html.Code("historical_currency_factors", className="mono"),
                            " que multiplica os valores antigos pelos fatores "
                            "cumulativos de reforma, deixando todos os anos em ",
                            html.Strong("R$ atual"),
                            ". O IPCA/IGP-M então só captura a inflação "
                            "residual — sem isso, valores pré-1994 seriam "
                            "10⁶–10⁹ vezes maiores que o devido.",
                        ],
                        className="page-sub",
                    ),
                ],
            ),
            html.Div(
                className="card subtle",
                children=[
                    section_header(
                        overline="Licença e atribuição",
                        title="Como citar este dashboard",
                    ),
                    html.Ul(
                        style={
                            "fontSize": "13.5px",
                            "color": "var(--fg-2)",
                            "lineHeight": "1.7",
                        },
                        children=[
                            html.Li(
                                [
                                    "Dados brutos: ",
                                    html.A(
                                        "IBGE PEVS (Pesquisa da Extração Vegetal "
                                        "e da Silvicultura)",
                                        href=(
                                            "https://www.ibge.gov.br/estatisticas/"
                                            "economicas/agricultura-e-pecuaria/"
                                            "9105-producao-da-extracao-vegetal-e-"
                                            "da-silvicultura.html"
                                        ),
                                        target="_blank",
                                    ),
                                    " e ",
                                    html.A(
                                        "BCB SGS (Sistema Gerenciador de Séries Temporais)",
                                        href="https://www3.bcb.gov.br/sgspub/",
                                        target="_blank",
                                    ),
                                    ".",
                                ]
                            ),
                            html.Li(
                                "Curadoria, enriquecimento e visualização: "
                                "Embrapa — Empresa Brasileira de Pesquisa "
                                "Agropecuária, vinculada ao Ministério da "
                                "Agricultura e Pecuária."
                            ),
                            html.Li(
                                "Reuso permitido sob a Lei de Acesso à Informação "
                                "(Lei nº 12.527/2011). Recomendamos citar "
                                "este dashboard junto com a fonte primária."
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _meta_row(label: str, value: str) -> html.Div:
    return html.Div(
        className="meta-row",
        children=[
            html.Span(label, className="meta-label"),
            html.Span(value, className="meta-val tnum"),
        ],
    )


def _bcb_series_table() -> object:
    data = [
        {
            "serie": "433",
            "nome": "IPCA mensal",
            "tipo": "Inflação",
            "uso": "val_real_ipca_*",
        },
        {
            "serie": "189",
            "nome": "IGP-M mensal",
            "tipo": "Inflação",
            "uso": "val_real_igpm_*",
        },
        {
            "serie": "190",
            "nome": "IGP-DI mensal",
            "tipo": "Inflação",
            "uso": "(disponível, não usado por padrão)",
        },
        {
            "serie": "3694",
            "nome": "USD/BRL — venda",
            "tipo": "Câmbio",
            "uso": "val_*_usd",
        },
        {
            "serie": "4393",
            "nome": "EUR/BRL — venda",
            "tipo": "Câmbio",
            "uso": "val_*_eur (a partir de 1999)",
        },
        {
            "serie": "20542",
            "nome": "CNY/BRL — venda",
            "tipo": "Câmbio",
            "uso": "val_*_cny",
        },
    ]
    return dash_table.DataTable(
        data=data,
        columns=[
            {"name": "Série SGS", "id": "serie"},
            {"name": "Nome", "id": "nome"},
            {"name": "Tipo", "id": "tipo"},
            {"name": "Uso no dashboard", "id": "uso"},
        ],
        style_cell={
            "fontFamily": "Univers, Verdana, Arial, sans-serif",
            "fontSize": "13px",
            "padding": "10px 12px",
            "border": "0",
            "borderBottom": "1px solid var(--border-subtle)",
            "backgroundColor": "#fff",
            "color": "var(--fg-2)",
        },
        style_cell_conditional=[
            {
                "if": {"column_id": "serie"},
                "fontFamily": "IBM Plex Mono, monospace",
                "fontSize": "12.5px",
            },
            {
                "if": {"column_id": "uso"},
                "fontFamily": "IBM Plex Mono, monospace",
                "fontSize": "12px",
                "color": "var(--embrapa-blue-darker)",
            },
        ],
        style_header={
            "backgroundColor": "var(--bg-surface-2)",
            "fontWeight": 500,
            "fontSize": "10px",
            "letterSpacing": "0.10em",
            "textTransform": "uppercase",
            "color": "var(--fg-3)",
            "border": "0",
            "borderBottom": "1px solid var(--border-default)",
        },
        style_as_list_view=True,
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    """Static page — no callbacks."""
    return None


__all__ = ["PREFIX", "layout", "register_callbacks"]
