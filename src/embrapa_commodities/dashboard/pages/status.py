"""/status — Saúde do sistema.

Surfaces the health registry: container info, stage ladder, BQ snapshot
state, and recent errors. Refreshes on demand via a Dash callback that
re-reads `health.snapshot()`. Doesn't touch BigQuery so it works even
when the rest of the dashboard is degraded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dash import Input, Output, dcc, html

from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import fmt_datetime
from embrapa_commodities.dashboard.health import health

PREFIX = "status"


def _fmt_seconds(s: float | None) -> str:
    if s is None:
        return "—"
    if s < 60:
        return f"{s:.1f} s"
    minutes, sec = divmod(int(s), 60)
    if minutes < 60:
        return f"{minutes} min {sec:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def _status_chip(status: str) -> html.Span:
    """Map stage.status → chip variant."""
    chip = {
        "ok": ("ok", "OK"),
        "running": ("info", "Carregando"),
        "pending": ("muted", "Aguardando"),
        "error": ("err", "Erro"),
    }.get(status, ("muted", status))
    return html.Span(chip[1], className=f"chip {chip[0]}")


def layout(store: GoldRepository) -> html.Div:
    """Initial layout. Most content comes via the refresh callback."""
    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=[
                    html.Div(
                        children=[
                            html.Div("Operação", className="overline"),
                            html.H1("Saúde do sistema", className="page-title"),
                            html.P(
                                "Estado de cada etapa de carregamento do dashboard, "
                                "metadados da instância em execução e histórico recente "
                                "de erros. Esta página não consulta o BigQuery — está "
                                "disponível mesmo quando o restante do dashboard falha.",
                                className="page-sub",
                            ),
                        ]
                    ),
                    html.Div(
                        className="hero-meta",
                        children=[
                            html.Div(
                                className="meta-row",
                                children=[
                                    html.Span("Atualizado em", className="meta-label"),
                                    html.Span(
                                        id={"section": PREFIX, "control": "now"},
                                        className="meta-val tnum",
                                    ),
                                ],
                            ),
                            html.Button(
                                "Atualizar agora",
                                id={"section": PREFIX, "control": "refresh"},
                                className="btn-secondary",
                                n_clicks=0,
                                style={"marginTop": "8px"},
                            ),
                        ],
                    ),
                ],
            ),
            # Auto-refresh every 5s so the page reflects current state without
            # needing the user to click. Cheap — only updates this page.
            dcc.Interval(
                id={"section": PREFIX, "control": "tick"},
                interval=5_000,
                n_intervals=0,
            ),
            html.Div(id={"section": PREFIX, "control": "container"}),
            html.Div(id={"section": PREFIX, "control": "stages"}),
            html.Div(id={"section": PREFIX, "control": "errors"}),
        ],
    )


# ── Section builders ──────────────────────────────────────────────────────


def _section_container(snap: dict[str, Any]) -> html.Div:
    return html.Div(
        className="card",
        children=[
            section_header(
                overline="Container",
                title="Identidade da instância em execução",
            ),
            html.Div(
                className="conv-grid",
                children=[
                    _info_card("Serviço", snap["service"]),
                    _info_card("Revision", snap["revision"]),
                    _info_card("Região", snap["region"]),
                ],
            ),
            html.Div(
                className="conv-grid",
                style={"marginTop": "12px"},
                children=[
                    _info_card("Iniciado em", fmt_datetime(snap["app_started_at"])),
                    _info_card("Uptime", _fmt_seconds(snap["uptime_seconds"])),
                    _info_card(
                        "Estado geral",
                        "100% operacional" if health.is_ready() else "Carregando",
                        tone="ok" if health.is_ready() else "info",
                    ),
                ],
            ),
        ],
    )


def _info_card(label: str, value: str, *, tone: str | None = None) -> html.Div:
    tag_style: dict[str, str] = {}
    if tone == "ok":
        tag_style = {"background": "rgba(0,111,53,0.10)", "color": "var(--embrapa-green-darker)"}
    elif tone == "err":
        tag_style = {"background": "rgba(178,58,43,0.10)", "color": "#8E2A1E"}
    elif tone == "info":
        tag_style = {"background": "rgba(6,97,124,0.10)", "color": "var(--embrapa-blue-darker)"}
    return html.Div(
        className="conv",
        children=[
            html.Div(label, className="overline", style={"marginBottom": "6px"}),
            html.Div(
                value,
                style={
                    "fontSize": "15px",
                    "fontWeight": 500,
                    "color": "var(--fg-1)",
                    "wordBreak": "break-word",
                    **tag_style,
                    "padding": "6px 10px" if tag_style else "0",
                    "borderRadius": "4px" if tag_style else "0",
                    "display": "inline-block" if tag_style else "block",
                },
            ),
        ],
    )


def _section_stages(snap: dict[str, Any]) -> html.Div:
    rows = []
    for stage in snap["stages"]:
        rows.append(
            html.Tr(
                children=[
                    html.Td(stage.label),
                    html.Td(_status_chip(stage.status)),
                    html.Td(
                        fmt_datetime(stage.started_at) if stage.started_at else "—",
                        className="tnum",
                        style={"fontFamily": "var(--font-mono)", "fontSize": "12px"},
                    ),
                    html.Td(
                        _fmt_seconds(stage.elapsed_seconds),
                        className="tnum num",
                    ),
                    html.Td(
                        stage.detail or "—",
                        style={"fontSize": "12.5px", "color": "var(--fg-2)"},
                    ),
                ]
            )
        )
    return html.Div(
        className="card",
        children=[
            section_header(
                overline="Etapas de carregamento",
                title="Pipeline de inicialização do dashboard",
                action=html.Span(
                    "100% operacional quando todas as etapas estão OK",
                    className="caption",
                ),
            ),
            html.Div(
                className="table-wrap",
                children=html.Table(
                    className="data-table",
                    children=[
                        html.Thead(
                            html.Tr(
                                children=[
                                    html.Th("Etapa"),
                                    html.Th("Status"),
                                    html.Th("Iniciado em"),
                                    html.Th("Duração", className="num"),
                                    html.Th("Detalhe"),
                                ]
                            )
                        ),
                        html.Tbody(rows),
                    ],
                ),
            ),
        ],
    )


def _section_errors(snap: dict[str, Any]) -> html.Div:
    errors = snap["errors"]
    if not errors:
        body = html.Div(
            className="empty-state",
            children="Nenhum erro registrado nesta instância.",
        )
    else:
        rows = []
        for err in errors[:10]:
            rows.append(
                html.Tr(
                    children=[
                        html.Td(
                            fmt_datetime(err["timestamp"]),
                            className="tnum",
                            style={"fontFamily": "var(--font-mono)", "fontSize": "12px"},
                        ),
                        html.Td(err.get("page", "—")),
                        html.Td(err.get("where", "—")),
                        html.Td(
                            err.get("type", "—"),
                            style={"fontFamily": "var(--font-mono)", "fontSize": "12px"},
                        ),
                        html.Td(
                            err.get("message", "—"),
                            style={
                                "fontFamily": "var(--font-mono)",
                                "fontSize": "12px",
                                "color": "var(--status-error)",
                                "maxWidth": "400px",
                                "wordBreak": "break-word",
                            },
                        ),
                    ]
                )
            )
        body = html.Div(
            className="table-wrap",
            children=html.Table(
                className="data-table",
                children=[
                    html.Thead(
                        html.Tr(
                            children=[
                                html.Th("Quando"),
                                html.Th("Página"),
                                html.Th("Onde"),
                                html.Th("Tipo"),
                                html.Th("Mensagem"),
                            ]
                        )
                    ),
                    html.Tbody(rows),
                ],
            ),
        )
    return html.Div(
        className="card",
        children=[
            section_header(
                overline=f"Erros recentes · {len(errors)} no histórico",
                title="Últimas falhas capturadas",
                action=html.Span(
                    "Limite de 20 entradas; mais antigas são descartadas",
                    className="caption",
                ),
            ),
            body,
        ],
    )


# ── Callbacks ─────────────────────────────────────────────────────────────


def register_callbacks(dash_app, store: GoldRepository) -> None:
    @dash_app.callback(
        Output({"section": PREFIX, "control": "now"}, "children"),
        Output({"section": PREFIX, "control": "container"}, "children"),
        Output({"section": PREFIX, "control": "stages"}, "children"),
        Output({"section": PREFIX, "control": "errors"}, "children"),
        Input({"section": PREFIX, "control": "tick"}, "n_intervals"),
        Input({"section": PREFIX, "control": "refresh"}, "n_clicks"),
    )
    def _refresh(_n_intervals, _n_clicks):
        snap = health.snapshot()
        return (
            fmt_datetime(datetime.now()),
            _section_container(snap),
            _section_stages(snap),
            _section_errors(snap),
        )


__all__ = ["PREFIX", "layout", "register_callbacks"]
