"""AppShell — institutional chrome wrapping every page.

Topbar (verde Embrapa), sidebar, content slot, and footer with the tríade
lockup. The shell is **source-aware**: when a `DataSource` is active, the
top nav renders that source's `primary_views`, and the sidebar lists the
available sources plus the active source's `sidebar_sections`.

On global pages (e.g. /status) there is no active source — the top nav
shows just the product name and the sidebar omits the per-source extras.
"""

from __future__ import annotations

from dash import dcc, html

from embrapa_commodities.dashboard.components.icons import icon
from embrapa_commodities.dashboard.data_sources import DataSource

# Single global sidebar section, always visible regardless of the
# active source. `/status` is the only global page so far.
_GLOBAL_SECTION = (("Saúde do sistema", "fact_check", "/status"),)


def _topbar(source: DataSource | None, view_id: str | None) -> html.Header:
    """Topbar with view tabs for the currently-active source.

    When no source is active (e.g. /status), the topbar shows just the
    product name without view tabs.
    """
    nav_items = []
    if source is not None:
        for v in source.primary_views:
            href = f"/{source.id}/{v.id}"
            is_active = v.id == view_id
            nav_items.append(
                dcc.Link(
                    v.label,
                    href=href,
                    className=f"topnav-item {'active' if is_active else ''}",
                )
            )

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
                    html.Span(
                        source.label if source is not None else "Embrapa",
                        className="util-chip",
                    ),
                ],
            ),
        ],
    )


def _sidebar(
    sources: list[DataSource],
    active_source: DataSource | None,
    active_view_id: str | None,
    path: str,
) -> html.Aside:
    """Sidebar with sources at top, active source's extras, then globals."""
    items: list = []

    # ── 1. Data sources ────────────────────────────────────────────────────
    items.append(html.Div("Bases de dados", className="side-section"))
    for src in sources:
        default_href = f"/{src.id}/{src.default_view().id}"
        # A source is "active" when its id appears in the active context,
        # regardless of which view is open.
        is_active = active_source is not None and active_source.id == src.id
        items.append(
            dcc.Link(
                children=[icon(src.icon), html.Span(src.label)],
                href=default_href,
                className=f"side-item {'active' if is_active else ''}",
            )
        )

    # ── 2. Active source's secondary sections ──────────────────────────────
    if active_source is not None:
        for section in active_source.sidebar_sections:
            items.append(html.Div(section.title, className="side-section"))
            for v in section.views:
                href = f"/{active_source.id}/{v.id}"
                is_active = v.id == active_view_id
                items.append(
                    dcc.Link(
                        children=[icon(v.icon), html.Span(v.label)],
                        href=href,
                        className=f"side-item {'active' if is_active else ''}",
                    )
                )

    # ── 3. Global section (always present) ─────────────────────────────────
    items.append(html.Div("Operação", className="side-section"))
    for label, ic, href in _GLOBAL_SECTION:
        is_active = path == href
        items.append(
            dcc.Link(
                children=[icon(ic), html.Span(label)],
                href=href,
                className=f"side-item {'active' if is_active else ''}",
            )
        )

    return html.Aside(
        className="sidebar",
        children=[
            *items,
            html.Div(
                className="side-foot",
                children=html.Div(
                    "Dados públicos · Pipeline Bronze → Silver → Gold sobre BigQuery.",
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


def shell(
    content,
    *,
    path: str,
    source: DataSource | None,
    view: object | None,
) -> html.Div:
    """Wrap a page's content in the full application shell.

    `source` is the active DataSource (None for global pages). `view`
    is the active View within that source (None when /<source> falls
    back to the default view, or for global pages).
    """
    # Late import to avoid a circular dependency between app and shell.
    from embrapa_commodities.dashboard.app import DATA_SOURCES

    sources = list(DATA_SOURCES.values())
    view_id = getattr(view, "id", None)

    return html.Div(
        className="shell",
        children=[
            _topbar(source, view_id),
            html.Div(
                className="body",
                children=[
                    _sidebar(sources, source, view_id, path),
                    html.Main(className="content", children=content),
                ],
            ),
            _footer(),
        ],
    )
