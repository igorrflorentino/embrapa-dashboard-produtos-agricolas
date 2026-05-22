"""/tabela — Tabela bruta do gold_commodity_matrix.

Exploration surface for the raw rows behind every chart in the dashboard.
Combines the standard filter bar with a free-text search box, a column
visibility toggle, paginated/sortable Dash DataTable, and the shared
"Exportar CSV" button that downloads exactly what's currently visible.
"""

from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.export import (
    COLUMN_LABELS,
    DEFAULT_COLUMNS,
    download_payload,
    export_button,
)
from embrapa_commodities.dashboard.components.filter_bar import filter_bar
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore
from embrapa_commodities.dashboard.formatting import fmt_currency, fmt_number

PREFIX = "tabela"

# Subset of columns shown by default to keep the table readable. The user
# can toggle the rest from the column picker. We keep the three currency
# columns out by default to avoid 22-column horizontal scrolling.
INITIAL_VISIBLE: tuple[str, ...] = (
    "reference_year",
    "state_acronym",
    "city_name",
    "product_description",
    "quantity_tons",
    "quantity_m3",
    "val_real_ipca_brl",
    "val_yearfx_brl",
    "data_quality_flag",
)


def _build_columns(visible: list[str]) -> list[dict]:
    """Dash DataTable column spec for the requested visible set."""
    cols: list[dict] = []
    for name in DEFAULT_COLUMNS:
        if name not in visible:
            continue
        is_numeric = name.startswith(("val_", "quantity_")) or name == "reference_year"
        cols.append(
            {
                "name": COLUMN_LABELS.get(name, name),
                "id": name,
                "type": "numeric" if is_numeric else "text",
            }
        )
    return cols


def _apply_search(df: pd.DataFrame, term: str | None) -> pd.DataFrame:
    if not term:
        return df
    term_lower = term.strip().lower()
    if not term_lower:
        return df
    string_cols = [
        "state_acronym",
        "state_name",
        "region",
        "city_name",
        "city_code",
        "product_description",
        "product_code",
        "data_quality_flag",
    ]
    string_cols = [c for c in string_cols if c in df.columns]
    if not string_cols:
        return df
    mask = pd.Series(False, index=df.index)
    for col in string_cols:
        mask = mask | df[col].astype(str).str.lower().str.contains(term_lower, na=False)
    return df[mask]


def _format_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Render numeric columns with pt-BR formatting for display.

    The underlying DataTable type stays 'numeric' so sorting still works
    correctly — we store the formatted string in a parallel column that the
    column spec points at. Simpler approach: cast all-numeric columns to
    pre-formatted strings AND keep the original sortable order via the
    DataTable's row order (rows are pre-sorted server-side before paging).
    """
    out = df.copy()
    for col in out.columns:
        if col.startswith("val_"):
            ccy = "BRL"
            if col.endswith("_usd"):
                ccy = "USD"
            elif col.endswith("_eur"):
                ccy = "EUR"
            elif col.endswith("_cny"):
                ccy = "CNY"
            out[col] = out[col].map(lambda v, c=ccy: fmt_currency(v, c) if pd.notna(v) else "—")
        elif col == "quantity_tons":
            out[col] = out[col].map(lambda v: fmt_number(v, unit="t") if pd.notna(v) else "—")
        elif col == "quantity_m3":
            out[col] = out[col].map(lambda v: fmt_number(v, unit="m³") if pd.notna(v) else "—")
        elif col == "reference_date":
            out[col] = out[col].map(lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) else "—")
        elif col == "last_refresh":
            out[col] = out[col].map(lambda v: v.strftime("%Y-%m-%d %H:%M") if pd.notna(v) else "—")
    return out


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
                            html.H1("Tabela bruta", className="page-title"),
                            html.P(
                                [
                                    "Linhas individuais de ",
                                    html.Code(
                                        "gold.gold_commodity_matrix",
                                        className="mono",
                                    ),
                                    f" — cobertura {lo}–{hi}. Use os filtros, a "
                                    "busca textual e o seletor de colunas para "
                                    "navegar. Tudo o que estiver visível pode ser "
                                    "exportado em CSV.",
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
                                children=export_button(
                                    button_id={"section": PREFIX, "control": "export"},
                                    download_id={"section": PREFIX, "control": "download"},
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            filter_bar(PREFIX, store),
            html.Div(
                className="filterbar",
                style={"gridTemplateColumns": "1fr 1fr", "marginTop": "8px"},
                children=[
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Busca textual"),
                            dcc.Input(
                                id={"section": PREFIX, "control": "search"},
                                type="text",
                                placeholder="Município, produto, UF, código...",
                                debounce=True,
                                style={"width": "100%"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Colunas visíveis"),
                            dcc.Dropdown(
                                id={"section": PREFIX, "control": "columns"},
                                options=column_options,
                                value=list(INITIAL_VISIBLE),
                                multi=True,
                                clearable=False,
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Resultado",
                        title="Linhas do recorte",
                        action=html.Span(
                            "Clique no cabeçalho para ordenar. Filtre por coluna "
                            "no ícone ↕ ao lado de cada nome.",
                            className="caption",
                        ),
                    ),
                    html.Div(
                        id={"section": PREFIX, "control": "table_wrap"},
                        className="table-wrap",
                    ),
                ],
            ),
        ],
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "table_wrap"}, "children"),
        Output({"section": PREFIX, "control": "rowcount"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "period"}, "value"),
        Input({"section": PREFIX, "control": "product"}, "value"),
        Input({"section": PREFIX, "control": "uf"}, "value"),
        Input({"section": PREFIX, "control": "conv"}, "value"),
        Input({"section": PREFIX, "control": "ccy"}, "value"),
        Input({"section": PREFIX, "control": "only_ok"}, "value"),
        Input({"section": PREFIX, "control": "search"}, "value"),
        Input({"section": PREFIX, "control": "columns"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _refresh(period, product, uf, conv, ccy, only_ok, search, visible_cols):
        try:
            years = _period_to_years(store, period)
            product_code = None if product in (None, "all") else product
            uf_code = None if uf in (None, "all") else uf
            only_ok_flag = bool(only_ok) and "ok" in (only_ok or [])

            df = store.filtered(
                years=years,
                product_code=product_code,
                state_acronym=uf_code,
                only_ok=only_ok_flag,
            )
            df = _apply_search(df, search)

            row_count = len(df)
            row_count_str = f"{row_count:,}".replace(",", ".")

            visible = visible_cols or list(INITIAL_VISIBLE)
            display_df = _format_for_display(df[[c for c in visible if c in df.columns]])

            table = dash_table.DataTable(
                data=display_df.head(5000).to_dict("records"),
                columns=_build_columns(visible),
                page_size=25,
                page_action="native",
                sort_action="native",
                filter_action="native",
                filter_options={"case": "insensitive"},
                style_table={"overflowX": "auto"},
                style_cell={
                    "fontFamily": "Univers, Verdana, Arial, sans-serif",
                    "fontSize": "13px",
                    "padding": "10px 12px",
                    "border": "0",
                    "borderBottom": "1px solid var(--border-subtle)",
                    "backgroundColor": "#fff",
                    "color": "var(--fg-2)",
                    "textAlign": "left",
                    "maxWidth": "280px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
                style_cell_conditional=[
                    {
                        "if": {"column_type": "numeric"},
                        "textAlign": "right",
                        "fontFamily": "IBM Plex Mono, monospace",
                        "fontSize": "12.5px",
                    }
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
                style_filter={
                    "backgroundColor": "#fff",
                    "borderBottom": "1px solid var(--border-subtle)",
                },
                style_data_conditional=[
                    {
                        "if": {
                            "filter_query": "{data_quality_flag} = 'OK'",
                            "column_id": "data_quality_flag",
                        },
                        "color": "var(--embrapa-green-darker)",
                        "fontWeight": 500,
                    },
                    {
                        "if": {
                            "filter_query": "{data_quality_flag} != 'OK' "
                            "&& {data_quality_flag} is not blank",
                            "column_id": "data_quality_flag",
                        },
                        "color": "var(--status-error)",
                        "fontWeight": 500,
                    },
                ],
            )

            note = None
            if row_count > 5000:
                note = html.Div(
                    f"Mostrando as primeiras 5.000 de {row_count_str} linhas. "
                    "Refine os filtros ou use Exportar CSV para o conjunto completo.",
                    className="caption",
                    style={
                        "padding": "10px 12px",
                        "background": "rgba(183,121,31,0.10)",
                        "color": "#8B5A14",
                        "borderRadius": "var(--radius-sm)",
                        "marginBottom": "8px",
                    },
                )

            children = [note, table] if note else table
            return children, row_count_str, no_update
        except Exception as exc:
            err = build_error_payload(exc, page="/tabela", where="callback da Tabela bruta")
            return no_update, no_update, err

    @dash_app.callback(
        Output({"section": PREFIX, "control": "download"}, "data"),
        Input({"section": PREFIX, "control": "export"}, "n_clicks"),
        State({"section": PREFIX, "control": "period"}, "value"),
        State({"section": PREFIX, "control": "product"}, "value"),
        State({"section": PREFIX, "control": "uf"}, "value"),
        State({"section": PREFIX, "control": "only_ok"}, "value"),
        State({"section": PREFIX, "control": "search"}, "value"),
        State({"section": PREFIX, "control": "columns"}, "value"),
        prevent_initial_call=True,
    )
    def _download(n_clicks, period, product, uf, only_ok, search, visible_cols):
        if not n_clicks:
            return no_update
        years = _period_to_years(store, period)
        product_code = None if product in (None, "all") else product
        uf_code = None if uf in (None, "all") else uf
        only_ok_flag = bool(only_ok) and "ok" in (only_ok or [])
        df = store.filtered(
            years=years,
            product_code=product_code,
            state_acronym=uf_code,
            only_ok=only_ok_flag,
        )
        df = _apply_search(df, search)
        return download_payload(
            df,
            filename_prefix="embrapa-tabela-bruta",
            columns=visible_cols or list(INITIAL_VISIBLE),
        )


def _period_to_years(store: GoldStore, period: str | None) -> tuple[int, int] | None:
    lo, hi = store.year_range()
    if period == "10":
        return (max(lo, hi - 9), hi)
    if period == "20":
        return (max(lo, hi - 19), hi)
    return None


__all__ = ["PREFIX", "layout", "register_callbacks"]
