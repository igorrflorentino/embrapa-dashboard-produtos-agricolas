"""Shared UI atoms: section headers, KPI cards, status tags, banners, page hero.

Ports of the prototype's ``Atoms.jsx`` / ``Sparkline.jsx`` / ``Status.jsx``,
returning Dash trees with the same class names so the verbatim CSS applies.
"""

from __future__ import annotations

from dash import html

from ..registries import Banco, maturity_meta
from .icons import icon

_DELTA_INK = {"up": "#003c1d", "down": "#8E2A1E"}


def section_header(overline: str, title: str, action=None) -> html.Div:
    children = [
        html.Div(
            [
                html.Div(overline, className="overline"),
                html.H3(title, className="section-title"),
            ]
        )
    ]
    if action is not None:
        children.append(html.Div(action, className="section-action"))
    return html.Div(children, className="section-head")


def card(children, *, subtle: bool = False, extra: str = "") -> html.Div:
    cls = "card" + (" subtle" if subtle else "") + (f" {extra}" if extra else "")
    return html.Div(children, className=cls)


def kpi_card(
    label,
    value: str,
    *,
    sub: str = "",
    delta: str | None = None,
    delta_positive: bool = True,
    spark=None,
) -> html.Div:
    """KPI card with optional sparkline (``charts.basic.sparkline_svg``) + delta."""
    top = [html.Div(label, className="kpi-ov")]
    if spark is not None:
        top.append(spark)
    sub_children = []
    if delta is not None:
        direction = "up" if delta_positive else "down"
        sub_children.append(
            html.Span(
                [
                    icon(
                        "arrow_upward" if delta_positive else "arrow_downward",
                        size=12,
                        color=_DELTA_INK[direction],
                    ),
                    html.Span(delta),
                ],
                className=f"kpi-delta {direction}",
            )
        )
    sub_children.append(html.Span(sub))
    return html.Div(
        [
            html.Div(top, className="kpi-top"),
            html.Div(value, className="kpi-val tnum"),
            html.Div(sub_children, className="kpi-sub"),
        ],
        className="kpi-card spark",
    )


def maturity_tag(banco: Banco, *, size: str | None = None) -> html.Span:
    m = maturity_meta(banco)
    cls = f"mat-tag mat-{m['id']}" + (" sm" if size == "sm" else "")
    return html.Span(
        [html.Span(className="mat-tag-dot", style={"background": m["color"]}), m["label"]],
        className=cls,
        title=m["desc"],
    )


def usage_dot(active: bool) -> html.Span:
    return html.Span(
        className="use-dot " + ("on" if active else "off"),
        title="Ativo · fonte dos dados em tela" if active else "Inativo",
    )


def usage_tag(active: bool) -> html.Span:
    return html.Span(
        [
            html.Span(className="use-dot " + ("on" if active else "off")),
            "Ativo" if active else "Inativo",
        ],
        className="use-tag " + ("on" if active else "off"),
    )


def maturity_banner(banco: Banco):
    """Caveat banner atop data views for beta/manutencao/descontinuado bancos."""
    m = maturity_meta(banco)
    if not m.get("caveat"):
        return None
    fallback = {
        "beta": "Cobertura ainda parcial — alguns períodos podem não estar completos e os "
        "valores podem mudar.",
        "manutencao": "Correção/atualização em andamento — alguns valores podem mudar.",
        "descontinuado": "Banco descontinuado e sem manutenção — será removido em breve.",
    }.get(m["id"], m["desc"])
    body = [html.Strong(f"{m['label']}."), " ", html.Span(banco.maturity_note or fallback)]
    if banco.maturity_date:
        body.append(html.Span(f" · {banco.maturity_date}", className="mat-banner-date tnum"))
    return html.Div(
        [
            html.Span(className="mat-banner-dot", style={"background": m["color"]}),
            html.Div(body, className="mat-banner-body"),
        ],
        className=f"mat-banner mat-banner-{m['id']}",
        style={"--st-color": m["color"]},
        role="status",
    )


def meta_group(head: str, rows: list[tuple[str, object]]) -> html.Div:
    """A provenance/selection block in the page hero (label/value rows)."""
    children = [html.Div(head, className="meta-group-head")]
    for label, value in rows:
        children.append(
            html.Div(
                [html.Span(label, className="meta-label"), html.Span(value, className="meta-val")],
                className="meta-row",
            )
        )
    return html.Div(children, className="meta-group")


def page_hero(overline: str, title: str, sub: str, meta_groups: list | None = None) -> html.Div:
    left = html.Div(
        [
            html.Div(overline, className="overline"),
            html.H1(title, className="page-title"),
            html.P(sub, className="page-sub"),
        ]
    )
    children = [left]
    if meta_groups:
        children.append(html.Div(meta_groups, className="hero-meta"))
    return html.Div(children, className="page-hero")
