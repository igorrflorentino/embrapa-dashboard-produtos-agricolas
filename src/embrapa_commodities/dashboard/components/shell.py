"""AppShell — institutional chrome wrapping every page.

Topbar (verde Embrapa), sidebar, content slot, and footer with the tríade
lockup. The active nav item is highlighted client-side by Dash's pathname
prop coming from `dcc.Location`.
"""

from __future__ import annotations

from dash import dcc, html

from embrapa_commodities.dashboard.components.icons import icon

NAV = [
    ("/", "Visão geral", "dashboard"),
    ("/produto", "Produto", "eco"),
    ("/geografia", "Geografia", "map"),
]

SIDEBAR_EXTRA = [
    ("Dados", [("Tabela bruta", "database"), ("Exportar CSV", "download"), ("Sobre a API", "api")]),
    ("Operação", [("Saúde do sistema", "fact_check", "/status")]),
    ("Sobre", [("Glossário", "help"), ("Sobre os dados", "info")]),
]


def _topbar(pathname: str) -> html.Header:
    nav_items = [
        dcc.Link(
            label,
            href=href,
            className=f"topnav-item {'active' if pathname == href else ''}",
        )
        for href, label, _ in NAV
    ]
    return html.Header(
        className="topbar",
        children=[
            html.Div(
                className="brand",
                children=html.Span(
                    "Embrapa",
                    className="brand-italic",
                    style={"fontSize": "22px", "color": "#fff"},
                ),
            ),
            html.Div(className="sep"),
            html.Div("Inteligência de Mercado — Commodities", className="product-name"),
            html.Nav(className="topnav", children=nav_items),
            html.Div(
                className="util",
                children=[
                    html.Span(
                        children=[icon("schedule", size=14), html.Span("Dados públicos")],
                        className="util-chip",
                    ),
                    html.Span("IBGE PEVS · BCB SGS", className="util-chip"),
                ],
            ),
        ],
    )


def _sidebar(pathname: str) -> html.Aside:
    primary_items = [
        dcc.Link(
            children=[icon(ic), html.Span(label)],
            href=href,
            className=f"side-item {'active' if pathname == href else ''}",
        )
        for href, label, ic in NAV
    ]

    extras: list = []
    for section_title, items in SIDEBAR_EXTRA:
        extras.append(html.Div(section_title, className="side-section"))
        for item in items:
            # Items are (label, icon) for inert entries or (label, icon, href)
            # for actual navigation links.
            if len(item) == 3:
                label, ic, href = item
                extras.append(
                    dcc.Link(
                        children=[icon(ic), html.Span(label)],
                        href=href,
                        className=(f"side-item {'active' if pathname == href else ''}"),
                    )
                )
            else:
                label, ic = item
                extras.append(
                    html.Div(
                        children=[icon(ic), html.Span(label)],
                        className="side-item",
                    )
                )

    return html.Aside(
        className="sidebar",
        children=[
            html.Div("Dashboards", className="side-section"),
            *primary_items,
            *extras,
            html.Div(
                className="side-foot",
                children=html.Div(
                    "Dados públicos · IBGE PEVS / BCB SGS. "
                    "Pipeline Bronze → Silver → Gold sobre BigQuery.",
                    className="public-note",
                ),
            ),
        ],
    )


def _footer() -> html.Footer:
    return html.Footer(
        className="footer",
        children=[
            html.Img(
                src="/assets/logos/triade-horizontal-black.png",
                alt="Embrapa · Ministério da Agricultura e Pecuária · Governo do Brasil",
                className="triade",
            ),
            html.Div(
                className="foot-meta",
                children=[
                    html.Div("© Empresa Brasileira de Pesquisa Agropecuária"),
                    html.Div(
                        "Ministério da Agricultura e Pecuária · "
                        "Pipeline Bronze → Silver → Gold · "
                        "BigQuery + Cloud Run",
                        className="caption",
                    ),
                    html.Div(
                        className="caption",
                        children=[
                            html.A(
                                "www.embrapa.br",
                                href="https://www.embrapa.br",
                                target="_blank",
                            ),
                            " · ",
                            html.A(
                                "Serviço de Atendimento ao Cidadão (SAC)",
                                href="https://www.embrapa.br/fale-conosco/sac",
                                target="_blank",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def shell(content, pathname: str) -> html.Div:
    """Wrap a page's content in the full application shell."""
    return html.Div(
        className="shell",
        children=[
            _topbar(pathname),
            html.Div(
                className="body",
                children=[
                    _sidebar(pathname),
                    html.Main(className="content", children=content),
                ],
            ),
            _footer(),
        ],
    )
