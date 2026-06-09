"""The institutional chrome: topbar, sidebar, perspective mega-menu, conventions
strip, filter trigger bar + modal, and footer. Render functions consumed by the
app's callbacks. Class names mirror ``AppShell.jsx`` so the verbatim CSS applies.
"""

from __future__ import annotations

# ruff: noqa: E501 — chrome module; long pt-BR UI copy strings are intentional.
from dash import dcc, html

from .. import format as fmt
from ..registries import (
    VIEW_GROUPS,
    banco_by_id,
    bancos_supporting,
    filter_schema_for,
    missing_caps_label,
    view_applies_to,
    view_by_id,
    visible_bancos,
)
from .cards import maturity_tag, usage_dot
from .icons import icon

_WHITE = "#ffffff"
_INK = "#333333"


# ── Topbar (static skeleton; nav label + menu filled by callbacks) ───────────
def topbar() -> html.Header:
    return html.Header(
        [
            html.Button(
                html.Img(
                    src="/assets/logo-embrapa-white-cropped.png",
                    alt="Embrapa",
                    className="brand-logo",
                ),
                className="brand brand-btn",
                id="brand-home",
                n_clicks=0,
                title="Voltar para Sobre o dashboard",
            ),
            html.Div(className="sep"),
            html.Div("Análise histórica de commodities", className="product-name"),
            html.Div(
                [
                    html.Button(
                        [icon("database", size=15, color=_WHITE), html.Span("Banco único")],
                        id="mode-single",
                        n_clicks=0,
                        className="mode-opt on",
                        role="tab",
                    ),
                    html.Button(
                        [icon("hub", size=15, color=_WHITE), html.Span("Multi-fonte")],
                        id="mode-multi",
                        n_clicks=0,
                        className="mode-opt",
                        role="tab",
                        title="Cruzar séries de bancos diferentes (em breve)",
                    ),
                ],
                className="mode-switch",
                role="tablist",
                **{"aria-label": "Modo de análise"},
            ),
            html.Nav(
                [
                    html.Button(
                        [
                            html.Span(id="nav-trigger-label", className="topnav-trigger-l"),
                            icon("expand_more", size=18, color=_WHITE),
                        ],
                        id="nav-trigger",
                        n_clicks=0,
                        className="topnav-trigger has-active",
                    ),
                    html.Div(id="navmenu"),
                ],
                className="topnav",
            ),
            html.Div(
                [
                    html.Button(
                        [icon("format_quote", size=16, color=_WHITE), html.Span("Citar painel")],
                        id="cite-open",
                        n_clicks=0,
                        className="util-action",
                    ),
                ],
                className="util",
            ),
        ],
        className="topbar",
    )


def footer() -> html.Footer:
    return html.Footer(
        [
            html.Img(
                src="/assets/triade-horizontal-black.png",
                className="triade",
                alt="Embrapa · Ministério da Agricultura e Pecuária · Governo do Brasil",
            ),
            html.Div(
                [
                    html.Div("© Empresa Brasileira de Pesquisa Agropecuária"),
                    html.Div(
                        "Ministério da Agricultura e Pecuária · Pipeline Bronze → Silver → Gold · "
                        "BigQuery + Cloud Run",
                        className="caption",
                    ),
                ],
                className="foot-meta",
            ),
        ],
        className="footer",
    )


# ── Sidebar (banco selector + info pages) ────────────────────────────────────
def sidebar(ui: dict) -> list:
    banco_id = ui.get("banco")
    info = ui.get("info")
    if ui.get("mode") == "multi":
        # Multi-fonte: the sidebar is a read-only "fontes incluídas" indicator,
        # not a clickable banco selector (the cross view picks its own sources).
        included = {s.get("b") for s in ((ui.get("cross") or {}).get("series") or [])}
        items = [
            html.Div("Fontes no cruzamento", className="side-section"),
            html.Div("Fontes combinadas no painel atual.", className="side-hint"),
        ]
        for b in visible_bancos():
            incl = b.id in included
            items.append(
                html.Div(
                    [
                        html.Span(className="side-src-dot"),
                        html.Span(b.short, className="side-src-name"),
                        html.Span("incluída", className="side-src-in")
                        if incl
                        else maturity_tag(b, size="sm"),
                    ],
                    className="side-src " + ("incl" if incl else "excl"),
                )
            )
    else:
        items = [html.Div("Banco de dados", className="side-section")]
        for b in visible_bancos():
            active = banco_id == b.id and not info
            selected = banco_id == b.id and info
            cls = "side-item" + (" active" if active else (" selected" if selected else ""))
            items.append(
                html.Div(
                    [
                        usage_dot(active),
                        html.Span(b.short, className="side-item-l"),
                        maturity_tag(b, size="sm"),
                    ],
                    className=cls,
                    id={"type": "banco", "id": b.id},
                    n_clicks=0,
                    title=b.label,
                )
            )
    items.append(html.Div("Informações", className="side-section"))
    for info_id, ic, label in [
        ("about", "info", "Sobre o dashboard"),
        ("glossary", "menu_book", "Glossário global"),
        ("health", "pulse", "Saúde do sistema"),
    ]:
        cls = "side-item" + (" active" if info == info_id else "")
        items.append(
            html.Div(
                [icon(ic, color=_INK), label],
                className=cls,
                id={"type": "info", "id": info_id},
                n_clicks=0,
            )
        )
    return items


# ── Perspective mega-menu ────────────────────────────────────────────────────
def nav_trigger_label(ui: dict) -> list:
    if ui.get("info"):
        return [html.Span("Selecionar perspectiva", className="topnav-trigger-view")]
    v = view_by_id(ui.get("view"))
    return [
        html.Span(v.group_label if v else "Perspectiva", className="topnav-trigger-grp"),
        html.Span(v.label if v else "Visão geral", className="topnav-trigger-view"),
    ]


def navmenu(ui: dict, nav_open: bool) -> list:
    if not nav_open:
        return []
    banco_id = ui.get("banco")
    is_multi = ui.get("mode") == "multi"
    groups = []
    for g in VIEW_GROUPS:
        gviews = [v for v in g.views if bool(v.cross_banco) == is_multi]
        if not gviews:
            continue
        opts = []
        for v in gviews:
            applies, missing = view_applies_to(v.id, banco_id)
            state = "na" if not applies else ("soon" if v.status == "soon" else "ok")
            active = (not ui.get("info")) and ui.get("view") == v.id
            tags = []
            if v.cross_banco:
                tags.append(html.Span("multi-fonte", className="topnav-opt-tag cross"))
            if state == "soon":
                tags.append(html.Span("Em breve", className="topnav-opt-tag soon"))
            if state == "na":
                tags.append(html.Span("Não se aplica", className="topnav-opt-tag na"))
            sup = bancos_supporting(v.id) if not applies else []
            opts.append(
                html.Button(
                    [
                        html.Span(
                            [
                                html.Span(className=f"topnav-opt-dot {state}"),
                                html.Span(v.label, className="topnav-opt-label"),
                                *tags,
                            ],
                            className="topnav-opt-top",
                        ),
                        html.Span(
                            "disponível em " + " · ".join(b.short for b in sup),
                            className="topnav-opt-supporters",
                        )
                        if sup
                        else html.Span(),
                    ],
                    className=f"topnav-opt state-{state}" + (" active" if active else ""),
                    id={"type": "view", "id": v.id},
                    n_clicks=0,
                    title=(f"Requer {missing_caps_label(missing)}" if not applies else v.desc),
                )
            )
        groups.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(g.label, className="topnav-grp-label"),
                            html.Span(g.hint, className="topnav-grp-hint"),
                        ],
                        className="topnav-grp-head",
                    ),
                    *opts,
                ],
                className="topnav-grp",
            )
        )

    scope = (
        html.Span(["Perspectivas ", html.Strong("multi-fonte"), " · entre bancos"])
        if is_multi
        else html.Span(["Perspectivas para ", html.Strong(banco_by_id(banco_id).short)])
    )
    legend = html.Span(
        [
            html.Span([html.Span(className="tnl-dot ok"), "Disponível"], className="tnl-item"),
            html.Span([html.Span(className="tnl-dot soon"), "Em breve"], className="tnl-item"),
            html.Span([html.Span(className="tnl-dot na"), "Não se aplica"], className="tnl-item"),
        ],
        className="topnav-menu-legend",
    )
    return [
        html.Div(className="topnav-scrim", id="nav-scrim", n_clicks=0),
        html.Div(
            [
                html.Div(
                    [html.Span(scope, className="topnav-menu-scope"), legend],
                    className="topnav-menu-bar",
                ),
                html.Div(groups, className="topnav-menu-grid"),
            ],
            className="topnav-menu" + (" narrow" if is_multi else ""),
            role="menu",
        ),
    ]


# ── Metric conventions strip ─────────────────────────────────────────────────
def _seg(group: str, options: list[tuple[str, str]], active: str) -> html.Div:
    return html.Div(
        [
            html.Button(
                [html.Span(opt_id, className="tnum"), html.Small(sub)],
                className="seg-opt" + (" on" if active == opt_id else ""),
                id={"type": "conv", "group": group, "value": opt_id},
                n_clicks=0,
            )
            for opt_id, sub in options
        ],
        className="seg",
    )


def conventions_strip(ui: dict) -> html.Div:
    conv = ui.get("conv", {})
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Convenções métricas", className="mc-overline"),
                    html.Span(
                        "Como os valores são exibidos — não altera quais linhas entram na "
                        "visualização. (Unidades físicas chegam numa próxima entrega.)",
                        className="mc-caption",
                    ),
                ],
                className="mc-head",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Moeda", className="mc-label"),
                            _seg(
                                "currency",
                                [("BRL", "R$"), ("USD", "US$"), ("EUR", "€"), ("CNY", "¥")],
                                conv.get("currency", "BRL"),
                            ),
                        ],
                        className="mc-group",
                    ),
                    html.Div(
                        [
                            html.Span("Correção monetária", className="mc-label"),
                            _seg(
                                "correction",
                                [
                                    ("Nominal", "sem corr."),
                                    ("IPCA", "IBGE"),
                                    ("IGP-M", "FGV"),
                                    ("IGP-DI", "FGV"),
                                ],
                                conv.get("correction", "IPCA"),
                            ),
                        ],
                        className="mc-group",
                    ),
                ],
                className="mc-groups",
            ),
        ],
        className="mc-bar",
    )


# ── Filter trigger bar + modal ───────────────────────────────────────────────
def _chips(ui: dict) -> tuple[str, str]:
    s = ui.get("summary", {})
    basket = s.get("basket")
    if basket is None:
        products = "Todos"
    elif len(basket) == 0:
        products = "Nenhum"
    else:
        products = f"{len(basket)} selecionado(s)"
    y0, y1 = s.get("startDate"), s.get("endDate")
    period = f"{str(y0)[:4]}–{str(y1)[:4]}" if (y0 or y1) else "Todo o período"
    return products, period


def filter_trigger_bar(ui: dict) -> html.Div:
    products, period = _chips(ui)
    return html.Div(
        [
            html.Span("Filtros ativos", className="fm-tb-label"),
            html.Span(
                [html.Span("Produtos", className="fm-chip-k"), products], className="fm-chip-filter"
            ),
            html.Span(
                [html.Span("Período", className="fm-chip-k"), period], className="fm-chip-filter"
            ),
            html.Span(className="fm-spacer"),
            html.Button(
                [icon("filter", size=13, color=_INK), " Editar filtros"],
                id="filter-open",
                n_clicks=0,
                className="fm-edit-btn",
            ),
        ],
        className="fm-trigger-bar",
    )


def filter_modal(ui: dict) -> html.Div:
    banco_id = ui.get("banco")
    banco = banco_by_id(banco_id)
    schema = filter_schema_for(banco_id)
    snap_products = _product_options(banco_id)
    s = ui.get("summary", {})
    y0 = int(str(s.get("startDate"))[:4]) if s.get("startDate") else None
    y1 = int(str(s.get("endDate"))[:4]) if s.get("endDate") else None
    cob = banco.cobertura or {}
    yr_lo, yr_hi = _coverage_years(cob)
    return html.Div(
        [
            html.Div(className="fm-backdrop", id="filter-close", n_clicks=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(f"Filtros · {banco.short}", className="fm-head-over"),
                                    html.H2("Editar filtros", className="fm-title"),
                                ],
                                className="fm-head-text",
                            ),
                            html.Button(
                                icon("close", size=18, color=_INK),
                                className="fm-close",
                                id="filter-close-x",
                                n_clicks=0,
                                **{"aria-label": "Fechar"},
                            ),
                        ],
                        className="fm-head",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        schema["dims"][0]["label"], className="fm-section-label"
                                    ),
                                    dcc.Dropdown(
                                        options=snap_products,
                                        value=s.get("basket"),
                                        multi=True,
                                        id="f-products",
                                        placeholder="Todos os produtos",
                                        className="fm-products",
                                    ),
                                ],
                                className="fm-section",
                            ),
                            html.Div(
                                [
                                    html.Div("Período", className="fm-section-label"),
                                    dcc.RangeSlider(
                                        min=yr_lo,
                                        max=yr_hi,
                                        value=[y0 or yr_lo, y1 or yr_hi],
                                        step=1,
                                        id="f-years",
                                        marks={yr_lo: str(yr_lo), yr_hi: str(yr_hi)},
                                        tooltip={"placement": "bottom", "always_visible": True},
                                    ),
                                ],
                                className="fm-section",
                            ),
                        ],
                        className="fm-body",
                    ),
                    html.Div(
                        [
                            html.Span(
                                [
                                    html.Span(className="fm-dot"),
                                    "Filtros enviados como SQL parametrizado ao BigQuery (pushdown).",
                                ],
                                className="fm-foot-info",
                            ),
                            html.Button(
                                "Limpar", id="f-clear", n_clicks=0, className="btn-secondary"
                            ),
                            html.Button(
                                "Aplicar filtros", id="f-apply", n_clicks=0, className="btn-primary"
                            ),
                        ],
                        className="fm-foot",
                    ),
                ],
                className="fm-modal",
            ),
        ],
        className="fm-root",
    )


def cite_modal(ui: dict) -> html.Div:
    banco = banco_by_id(ui.get("banco"))
    v = view_by_id(ui.get("view"))
    conv = ui.get("conv", {})
    citation = (
        "EMPRESA BRASILEIRA DE PESQUISA AGROPECUÁRIA (EMBRAPA). "
        f"Dashboard de Análise Histórica de Commodities — {banco.short} — "
        f"{v.label if v else 'Visão geral'}. "
        f"Convenções métricas: {fmt.convention_monetary_label(conv)}. "
        "Brasília: Embrapa, 2026."
    )
    return html.Div(
        [
            html.Div(className="cite-backdrop", id="cite-close", n_clicks=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Citação acadêmica", className="overline"),
                                    html.H2("Citar painel · ABNT NBR 6023"),
                                ]
                            ),
                            html.Button(
                                icon("close", size=18, color=_INK),
                                className="fm-close",
                                id="cite-close-x",
                                n_clicks=0,
                                **{"aria-label": "Fechar"},
                            ),
                        ],
                        className="cite-head",
                    ),
                    html.Div([html.Pre(citation, className="cite-text")], className="cite-body"),
                ],
                className="cite-modal",
            ),
        ],
        className="cite-root",
    )


def _product_options(banco_id: str) -> list[dict]:
    """Product dropdown options from the live snapshot (best-effort)."""
    try:
        from .. import seam

        snap = seam.snapshot(banco_id, {"currency": "BRL", "correction": "IPCA"}, None)
        products = snap.get("products")
        if products is not None and not products.empty:
            return [
                {"label": f"{r['name']} ({r['code']})", "value": str(r["code"])}
                for _, r in products.iterrows()
            ]
    except Exception:  # pragma: no cover - dropdown still works empty
        pass
    return []


def _coverage_years(cobertura: dict) -> tuple[int, int]:
    years = str(cobertura.get("years", ""))
    digits = [int(t) for t in years.replace("→", " ").split() if t.isdigit()]
    lo = digits[0] if digits else 1986
    return lo, 2026
