"""/glossario — Glossário de termos."""

from __future__ import annotations

from dash import html

from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository

PREFIX = "glossario"


def _term(term: str, definition, *, source: str | None = None) -> html.Div:
    """Render a single glossary entry as a definition row."""
    return html.Div(
        className="glossary-row",
        style={
            "display": "grid",
            "gridTemplateColumns": "minmax(180px, 240px) 1fr",
            "gap": "20px",
            "padding": "14px 0",
            "borderBottom": "1px solid var(--border-subtle)",
        },
        children=[
            html.Div(
                children=[
                    html.Div(term, style={"fontWeight": 500, "color": "var(--fg-1)"}),
                    html.Div(
                        source,
                        className="caption",
                        style={"marginTop": "4px"},
                    )
                    if source
                    else None,
                ],
            ),
            html.Div(
                definition,
                style={"color": "var(--fg-2)", "fontSize": "13.5px", "lineHeight": "1.6"},
            ),
        ],
    )


def _section(*, title: str, overline: str, terms: list[html.Div]) -> html.Div:
    return html.Div(
        className="card",
        children=[
            section_header(overline=overline, title=title),
            html.Div(terms),
        ],
    )


def layout(store: GoldRepository) -> html.Div:
    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=html.Div(
                    children=[
                        html.Div("Referência", className="overline"),
                        html.H1("Glossário", className="page-title"),
                        html.P(
                            "Termos e siglas usados ao longo do dashboard, "
                            "ordenados por tema. Em dúvida sobre uma coluna ou "
                            "convenção? Comece por aqui.",
                            className="page-sub",
                        ),
                    ]
                ),
            ),
            _section(
                overline="Convenções monetárias",
                title="Como ler as colunas val_*",
                terms=[
                    _term(
                        html.Code("val_real_ipca_*", className="mono"),
                        [
                            "Valor projetado para os preços de hoje pela ",
                            html.Strong("cadeia mensal do IPCA"),
                            " (BCB SGS série 433). Use esta convenção para ",
                            html.Strong("comparações entre anos"),
                            " — ela neutraliza inflação e mantém a moeda na "
                            "base atual. Padrão do dashboard.",
                        ],
                        source="Fonte: dbt/models/silver/silver_bcb_inflation.sql",
                    ),
                    _term(
                        html.Code("val_real_igpm_*", className="mono"),
                        [
                            "Idem ao anterior, usando o ",
                            html.Strong("IGP-M"),
                            " (BCB SGS série 189) como índice. Alternativa "
                            "institucional ao IPCA, com maior aderência a "
                            "séries de commodities (preços no atacado).",
                        ],
                    ),
                    _term(
                        html.Code("val_yearfx_*", className="mono"),
                        [
                            "Valor em R$ correntes convertido pelo câmbio ",
                            html.Strong("médio do ano de referência"),
                            ". Útil para ",
                            html.Strong("auditoria histórica"),
                            " (qual era o valor em USD/EUR/CNY quando a transação aconteceu) — ",
                            html.Strong("não use para comparar anos"),
                            " entre si, pois cada ano tem sua própria FX. "
                            "Colunas USD/EUR/CNY ficam NULL antes de 1994.",
                        ],
                    ),
                ],
            ),
            _section(
                overline="Qualidade de dados",
                title="Valores de data_quality_flag",
                terms=[
                    _term(
                        html.Code("OK", className="mono"),
                        "A linha tem quantidade (tons ou m³) e valor monetário. "
                        "Pode entrar em qualquer agregação sem ressalvas.",
                    ),
                    _term(
                        html.Code("MISSING_VALUE", className="mono"),
                        "A quantidade existe, mas o valor monetário está ausente "
                        "no SIDRA. Útil para análises de volume, mas não para "
                        "totais financeiros.",
                    ),
                    _term(
                        html.Code("MISSING_QUANTITY", className="mono"),
                        "O valor monetário existe, mas a quantidade está ausente. "
                        "Raro — normalmente o IBGE publica os dois ou nenhum.",
                    ),
                    _term(
                        html.Code("INCOMPLETE", className="mono"),
                        "Ambos ausentes — a linha existe apenas como registro de "
                        "que aquele município/produto foi pesquisado mas sem "
                        "valor coletado.",
                    ),
                ],
            ),
            _section(
                overline="Siglas e fontes",
                title="O que cada acrônimo significa",
                terms=[
                    _term(
                        "IBGE",
                        "Instituto Brasileiro de Geografia e Estatística — órgão "
                        "público federal responsável pela coleta de estatísticas "
                        "demográficas, econômicas e geográficas do Brasil.",
                    ),
                    _term(
                        "PEVS",
                        "Pesquisa da Extração Vegetal e da Silvicultura — pesquisa "
                        "anual do IBGE que mensura a produção dos produtos do "
                        "extrativismo vegetal e da silvicultura nos municípios "
                        "brasileiros. Tabela SIDRA 289.",
                    ),
                    _term(
                        "SIDRA",
                        "Sistema IBGE de Recuperação Automática — portal oficial "
                        "de consulta às pesquisas e tabelas do IBGE.",
                    ),
                    _term(
                        "BCB",
                        "Banco Central do Brasil — autoridade monetária responsável "
                        "pelas séries oficiais de inflação, câmbio e juros.",
                    ),
                    _term(
                        "SGS",
                        "Sistema Gerenciador de Séries Temporais — API pública do "
                        "BCB para consulta às séries macroeconômicas oficiais.",
                    ),
                    _term(
                        "IPCA",
                        "Índice Nacional de Preços ao Consumidor Amplo — calculado "
                        "pelo IBGE, é a referência oficial para a meta de "
                        "inflação do Brasil. BCB SGS série 433.",
                    ),
                    _term(
                        "IGP-M",
                        "Índice Geral de Preços do Mercado — calculado pela FGV, "
                        "composto por 60% IPA (atacado) + 30% IPC (consumidor) + "
                        "10% INCC (construção civil). BCB SGS série 189.",
                    ),
                    _term(
                        "Tríade",
                        "Composição institucional Embrapa + Ministério da "
                        "Agricultura e Pecuária + Governo do Brasil (Do Lado do "
                        "Povo Brasileiro) — assinatura conjunta obrigatória em "
                        "veículos públicos da Embrapa.",
                    ),
                ],
            ),
            _section(
                overline="Arquitetura",
                title="Camadas do pipeline (Medalhão)",
                terms=[
                    _term(
                        "Bronze",
                        [
                            "Camada de ingestão: cópia fiel dos dados brutos do "
                            "IBGE/BCB, sem transformação. Todas as colunas como ",
                            html.Code("STRING", className="mono"),
                            ", append-only, particionada por ",
                            html.Code("ingestion_timestamp", className="mono"),
                            ".",
                        ],
                    ),
                    _term(
                        "Silver",
                        "Camada de tipagem e enriquecimento: aplica fatores "
                        "históricos de moeda (Cz$ → Cr$ → R$), encadeia o IPCA "
                        "e o IGP-M, deduplica por chave natural.",
                    ),
                    _term(
                        "Gold",
                        [
                            "Camada analítica: ",
                            html.Code("gold.gold_commodity_matrix", className="mono"),
                            ". Uma linha por (ano, estado, município, produto), "
                            "com 12 colunas de valor monetário cobrindo IPCA, "
                            "IGP-M e FX-do-ano em BRL, USD, EUR e CNY.",
                        ],
                    ),
                ],
            ),
        ],
    )


def register_callbacks(dash_app, store: GoldRepository) -> None:
    """Static page — no callbacks."""
    return None


__all__ = ["PREFIX", "layout", "register_callbacks"]
