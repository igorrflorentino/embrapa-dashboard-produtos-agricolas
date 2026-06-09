"""Placeholder + info screens: coming-soon, não-se-aplica, perspective-soon, about, health."""

from __future__ import annotations

# ruff: noqa: E501 — presentation module; long pt-BR UI copy strings are intentional.
from dash import html

from ..components.cards import card, maturity_tag, section_header
from ..components.icons import icon
from ..registries import Banco, banco_availability, banco_by_id, view_by_id, visible_bancos


def coming_soon(banco: Banco, view_id: str) -> html.Div:
    """Whole-banco placeholder (banco has no Gold table yet) — PAM / SEFAZ."""
    cobertura = banco.cobertura or {}
    caption = (
        "sem prazo definido"
        if banco.maturity == "planejado"
        else f"previsão · {banco.maturity_date or '—'}"
    )
    cov_rows = []
    for dt, key in [
        ("Cobertura temporal", "years"),
        ("Cadência de atualização", "atualizacao"),
        ("Granularidade da Gold", "granularidade"),
        ("Restrições", "restricoes"),
    ]:
        if cobertura.get(key):
            mono = "mono" if key == "granularidade" else None
            cov_rows += [html.Dt(dt), html.Dd(cobertura[key], className=mono)]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [maturity_tag(banco), html.Span(caption, className="caption")],
                                className="cs-eyebrow",
                            ),
                            html.H2(banco.label, className="cs-title"),
                            html.P(banco.sub, className="cs-sub"),
                        ],
                        className="cs-hero-l",
                    ),
                    html.Div(
                        [
                            _meta_row("Domínio", banco.domain),
                            _meta_row("Granularidade", banco.scope),
                            _meta_row("Fonte", banco.source),
                            _meta_row("Tabela Gold", html.Code(banco.table)),
                        ],
                        className="cs-hero-r",
                    ),
                ],
                className="cs-hero",
            ),
            html.Div(
                [
                    card(
                        [
                            section_header(
                                "Cobertura prevista", "O que esperar quando o banco for liberado"
                            ),
                            html.Dl(cov_rows, className="cs-cov"),
                            html.Div(
                                [
                                    icon("info", size=14, color="#06617c"),
                                    html.Span(
                                        [
                                            f"A perspectiva ({_view_label(view_id)}) será habilitada "
                                            "automaticamente assim que o backend publicar a tabela ",
                                            html.Code(banco.table),
                                            ". Os componentes de visualização já existem e serão reaproveitados.",
                                        ]
                                    ),
                                ],
                                className="cs-note",
                            ),
                        ]
                    ),
                ],
                className="grid-1 cs-grid",
            ),
        ],
        className="cs-stack",
    )


def perspective_soon(view_id: str) -> html.Div:
    """View-level placeholder: banco is live, but this perspective isn't built yet."""
    v = view_by_id(view_id)
    label = v.label if v else view_id
    desc = v.desc if v else ""
    group = f"{v.group_label}" if v else ""
    return html.Div(
        [
            card(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("Em breve", className="cs-badge"),
                                    html.Span(group, className="caption"),
                                ],
                                className="cs-eyebrow",
                            ),
                            html.H2(label, className="cs-title"),
                            html.P(desc, className="cs-sub"),
                        ],
                        className="ps-hero-l",
                    ),
                ],
                extra="ps-hero",
            ),
            card(
                [
                    section_header("Sobre esta perspectiva", "Já prevista na arquitetura"),
                    html.Div(
                        [
                            icon("info", size=14, color="#06617c"),
                            html.Span(
                                "Esta perspectiva chega numa próxima entrega (M2/M3 do handoff). "
                                "Os filtros e convenções métricas selecionados serão aplicados "
                                "automaticamente assim que ela for publicada — sem reconfigurar a análise."
                            ),
                        ],
                        className="cs-note",
                    ),
                ]
            ),
        ],
        className="cs-stack",
    )


def not_applicable(
    view_id: str, banco: Banco, missing_label: str, supporters: list[Banco]
) -> html.Div:
    """Capability mismatch: the view needs a dimension this banco lacks."""
    v = view_by_id(view_id)
    head = card(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Não se aplica", className="na-badge"),
                            html.Span(f"{v.group_label}" if v else "", className="caption"),
                        ],
                        className="cs-eyebrow",
                    ),
                    html.H2(v.label if v else view_id, className="cs-title"),
                    html.P(
                        [
                            "Esta perspectiva não está disponível para ",
                            html.Strong(banco.short),
                            ", que não possui ",
                            html.Strong(missing_label or "a dimensão necessária"),
                            ".",
                        ],
                        className="cs-sub",
                    ),
                    html.P(v.desc if v else "", className="cs-sub na-desc"),
                ],
                className="na-hero-l",
            ),
        ],
        extra="na-hero",
    )
    if not supporters:
        body = card(
            html.P(
                "Nenhum banco disponível oferece esta perspectiva no momento.",
                className="caption",
                style={"padding": "16px 4px"},
            ),
            subtle=True,
        )
        return html.Div([head, body], className="cs-stack")
    bancos = html.Div(
        [
            html.Button(
                [
                    html.Div(
                        [
                            html.Span(b.short, className="na-banco-short"),
                            html.Span(banco_availability(b), className=f"na-banco-tag {b.status}"),
                        ],
                        className="na-banco-head",
                    ),
                    html.Div(b.domain, className="na-banco-domain"),
                    html.P(b.sub, className="na-banco-sub"),
                    html.Span("Trocar para este banco →", className="na-banco-cta")
                    if b.status == "live"
                    else html.Span(),
                ],
                className=f"na-banco {'live' if b.status == 'live' else 'soon'}",
                id={"type": "pick-banco", "id": b.id},
                n_clicks=0,
            )
            for b in supporters
        ],
        className="na-bancos",
    )
    return html.Div(
        [
            head,
            card(
                [
                    section_header(
                        "Onde usar esta perspectiva",
                        "Bancos compatíveis",
                        action=html.Span(
                            f"{len(supporters)} de {len(visible_bancos())} bancos",
                            className="caption",
                        ),
                    ),
                    bancos,
                ]
            ),
        ],
        className="cs-stack",
    )


def about() -> html.Div:
    """'Sobre o dashboard' info page."""
    bancos = visible_bancos()
    rows = [
        html.Div(
            [
                html.Div(
                    [maturity_tag(b, size="sm"), html.Code(b.table)], className="about-banco-head"
                ),
                html.Div(b.label, className="about-banco-label"),
                html.P(b.sub, className="caption"),
            ],
            className="about-banco",
        )
        for b in bancos
    ]
    return html.Div(
        [
            card(
                [
                    section_header("Visão do produto", "Inteligência de mercado de commodities"),
                    html.P(
                        "Painel científico para análise histórica de commodities brasileiras. "
                        "O pipeline Medalhão (Bronze → Silver → Gold) no BigQuery alimenta marts "
                        "pré-agregados; este painel consulta esses marts sob demanda (Pushdown "
                        "Computing) e nunca mantém a Gold em memória.",
                        className="p",
                    ),
                ]
            ),
            card(
                [
                    section_header(
                        "Bancos de dados",
                        "Fontes que compõem a base",
                        action=html.Span(f"{len(bancos)} bancos", className="caption"),
                    ),
                    html.Div(rows, className="about-bancos"),
                ]
            ),
        ],
        className="cs-stack",
    )


def health() -> html.Div:
    """'Saúde do sistema' info page — maturity + table per banco."""
    rows = [
        html.Div(
            [
                html.Span(b.short, className="health-short"),
                maturity_tag(b, size="sm"),
                html.Code(b.table, className="health-table"),
                html.Span(
                    "Saudável" if b.has_data else "Aguardando ingestão",
                    className="health-state " + ("ok" if b.has_data else "wait"),
                ),
            ],
            className="health-row",
        )
        for b in visible_bancos()
    ]
    return html.Div(
        [
            card(
                [
                    section_header("Estado dos bancos", "Maturidade e disponibilidade"),
                    html.Div(rows, className="health-list"),
                    html.Div(
                        [
                            icon("info", size=14, color="#06617c"),
                            html.Span(
                                "Maturidade é uma propriedade de build (lifecycle do dataset); "
                                "a saúde operacional (execuções, frescor) é derivada em tempo real "
                                "e será detalhada numa próxima entrega."
                            ),
                        ],
                        className="cs-note",
                    ),
                ]
            ),
        ],
        className="cs-stack",
    )


def _meta_row(label: str, value) -> html.Div:
    return html.Div(
        [html.Span(label, className="meta-label"), html.Span(value, className="meta-val")],
        className="cs-meta-row",
    )


def _view_label(view_id: str) -> str:
    v = view_by_id(view_id)
    return v.label if v else view_id


def supporters_for(view_id: str):
    """Bancos that support a view (for the não-se-aplica inverse indicator)."""
    from ..registries import bancos_supporting

    return bancos_supporting(view_id)


def resolve_banco(banco_id: str) -> Banco:
    return banco_by_id(banco_id)
