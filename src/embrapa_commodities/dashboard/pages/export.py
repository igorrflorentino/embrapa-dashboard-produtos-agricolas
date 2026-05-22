"""/export — Exportação completa em CSV.

Standalone export surface: pick filters, choose columns, optionally include
the entire snapshot, then download. Distinct from the inline "Exportar
CSV" buttons in the analytical pages, which export just the filters used
on that specific page.
"""

from __future__ import annotations

from dash import Input, Output, State, dcc, html, no_update

from embrapa_commodities.dashboard.components.export import (
    COLUMN_LABELS,
    DEFAULT_COLUMNS,
    download_payload,
)
from embrapa_commodities.dashboard.components.filter_bar import filter_bar
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore

PREFIX = "export"


def layout(store: GoldStore) -> html.Div:
    lo, hi = store.year_range()
    column_options = [{"label": COLUMN_LABELS.get(c, c), "value": c} for c in DEFAULT_COLUMNS]

    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=[
                    html.Div(
                        children=[
                            html.Div("Dados", className="overline"),
                            html.H1("Exportar CSV", className="page-title"),
                            html.P(
                                [
                                    "Baixe o recorte filtrado de ",
                                    html.Code(
                                        "gold.gold_commodity_matrix",
                                        className="mono",
                                    ),
                                    f" no formato CSV pt-BR (separador `;`, decimal "
                                    f"`,`, UTF-8). Cobertura disponível: {lo}–{hi}.",
                                ],
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
                                    html.Span("Linhas no recorte", className="meta-label"),
                                    html.Span(
                                        id={"section": PREFIX, "control": "rowcount"},
                                        className="meta-val tnum",
                                    ),
                                ],
                            ),
                            html.Div(
                                style={"display": "flex", "gap": "8px", "marginTop": "8px"},
                                children=[
                                    html.Button(
                                        "Baixar CSV",
                                        id={"section": PREFIX, "control": "download_btn"},
                                        n_clicks=0,
                                        className="btn-primary",
                                        type="button",
                                    ),
                                    dcc.Download(id={"section": PREFIX, "control": "download"}),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            filter_bar(PREFIX, store),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Configuração avançada",
                        title="Colunas e escopo",
                    ),
                    html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "1fr 1fr",
                            "gap": "16px",
                            "alignItems": "start",
                            "marginTop": "12px",
                        },
                        children=[
                            html.Div(
                                children=[
                                    html.Label(
                                        "Colunas a incluir",
                                        className="overline",
                                        style={"marginBottom": "6px", "display": "block"},
                                    ),
                                    dcc.Dropdown(
                                        id={"section": PREFIX, "control": "columns"},
                                        options=column_options,
                                        value=list(DEFAULT_COLUMNS),
                                        multi=True,
                                        clearable=False,
                                    ),
                                    html.Div(
                                        "Por padrão todas as 25 colunas do Gold são "
                                        "incluídas. Remova as que não interessam para "
                                        "deixar o arquivo mais leve.",
                                        className="caption",
                                        style={"marginTop": "6px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Escopo de linhas",
                                        className="overline",
                                        style={"marginBottom": "6px", "display": "block"},
                                    ),
                                    dcc.RadioItems(
                                        id={"section": PREFIX, "control": "scope"},
                                        options=[
                                            {
                                                "label": " Aplicar os filtros acima",
                                                "value": "filtered",
                                            },
                                            {
                                                "label": " Todo o snapshot (ignora filtros)",
                                                "value": "all",
                                            },
                                        ],
                                        value="filtered",
                                        labelStyle={
                                            "display": "block",
                                            "padding": "4px 0",
                                            "fontSize": "13px",
                                        },
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card subtle",
                children=[
                    section_header(
                        overline="Formato",
                        title="Detalhes técnicos do arquivo",
                    ),
                    html.Ul(
                        style={"fontSize": "13px", "color": "var(--fg-2)", "lineHeight": "1.7"},
                        children=[
                            html.Li(
                                [
                                    "Encoding: ",
                                    html.Code("UTF-8", className="mono"),
                                    " (compatível com Excel pt-BR, LibreOffice, Pandas).",
                                ]
                            ),
                            html.Li(
                                [
                                    "Separador de campos: ",
                                    html.Code(";", className="mono"),
                                    " (ponto-e-vírgula — padrão Excel pt-BR).",
                                ]
                            ),
                            html.Li(
                                [
                                    "Separador decimal: ",
                                    html.Code(",", className="mono"),
                                    " (vírgula).",
                                ]
                            ),
                            html.Li("Formato de datas: ISO 8601 (AAAA-MM-DD)."),
                            html.Li(
                                "Linha de cabeçalho com labels em português; "
                                "consulte o Glossário para definição de cada coluna."
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "rowcount"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "period"}, "value"),
        Input({"section": PREFIX, "control": "product"}, "value"),
        Input({"section": PREFIX, "control": "uf"}, "value"),
        Input({"section": PREFIX, "control": "only_ok"}, "value"),
        Input({"section": PREFIX, "control": "scope"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _rowcount(period, product, uf, only_ok, scope):
        try:
            if scope == "all":
                rows = len(store.df())
            else:
                rows = len(_filtered(store, period, product, uf, only_ok))
            return f"{rows:,}".replace(",", "."), no_update
        except Exception as exc:
            err = build_error_payload(exc, page="/export", where="contagem de linhas (Exportar)")
            return no_update, err

    @dash_app.callback(
        Output({"section": PREFIX, "control": "download"}, "data"),
        Input({"section": PREFIX, "control": "download_btn"}, "n_clicks"),
        State({"section": PREFIX, "control": "period"}, "value"),
        State({"section": PREFIX, "control": "product"}, "value"),
        State({"section": PREFIX, "control": "uf"}, "value"),
        State({"section": PREFIX, "control": "only_ok"}, "value"),
        State({"section": PREFIX, "control": "scope"}, "value"),
        State({"section": PREFIX, "control": "columns"}, "value"),
        prevent_initial_call=True,
    )
    def _download(n_clicks, period, product, uf, only_ok, scope, columns):
        if not n_clicks:
            return no_update
        if scope == "all":
            df = store.df()
            prefix = "embrapa-gold-completo"
        else:
            df = _filtered(store, period, product, uf, only_ok)
            prefix = "embrapa-gold-filtrado"
        return download_payload(df, filename_prefix=prefix, columns=columns)


def _filtered(store: GoldStore, period, product, uf, only_ok):
    years = _period_to_years(store, period)
    product_code = None if product in (None, "all") else product
    uf_code = None if uf in (None, "all") else uf
    only_ok_flag = bool(only_ok) and "ok" in (only_ok or [])
    return store.filtered(
        years=years,
        product_code=product_code,
        state_acronym=uf_code,
        only_ok=only_ok_flag,
    )


def _period_to_years(store: GoldStore, period: str | None) -> tuple[int, int] | None:
    lo, hi = store.year_range()
    if period == "10":
        return (max(lo, hi - 9), hi)
    if period == "20":
        return (max(lo, hi - 19), hi)
    return None


__all__ = ["PREFIX", "layout", "register_callbacks"]
