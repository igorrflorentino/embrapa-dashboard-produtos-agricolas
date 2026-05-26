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
from embrapa_commodities.dashboard.formatting import period_to_years

# Hard cap on rows sent to the client. The DataTable paginates client-side,
# but the JSON payload includes every row — without this cap a 90k-row
# snapshot would push ~5 MB to the browser per filter change, freezing
# navigation. For the full dataset the user should use /export.
MAX_DISPLAY_ROWS = 1000

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
    """Dash DataTable column spec for the requested visible set.

    Numbers use the DataTable's native pt-BR-leaning format spec
    (thousand-sep `.`, decimal `,`) so the rows can ship as raw floats
    instead of pre-formatted strings — ~5x smaller payload.
    """
    cols: list[dict] = []
    for name in DEFAULT_COLUMNS:
        if name not in visible:
            continue
        col: dict = {"name": COLUMN_LABELS.get(name, name), "id": name}
        if name == "reference_year":
            col["type"] = "numeric"
            col["format"] = {"specifier": "d"}
        elif name.startswith("val_"):
            col["type"] = "numeric"
            col["format"] = {
                "specifier": ",.2f",
                "locale": {"group": ".", "decimal": ","},
            }
        elif name.startswith("quantity_"):
            col["type"] = "numeric"
            col["format"] = {
                "specifier": ",.0f",
                "locale": {"group": ".", "decimal": ","},
            }
        else:
            col["type"] = "text"
        cols.append(col)
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


def _quality_flag_styling() -> list[dict]:
    """Style the data_quality_flag column by exact value.

    Earlier versions used `!= 'OK' && {col} is not blank` to color any
    non-OK flag red, but that compound filter query crashes Dash 4's
    filter parser ("DataTable filtering syntax is invalid"), which in
    turn prevents the entire DataTable from rendering. Listing each
    known flag value explicitly is uglier but works on every Dash
    version and is robust to future operator changes.
    """
    base_style = {"fontWeight": 500}
    rules: list[dict] = [
        {
            "if": {
                "filter_query": '{data_quality_flag} eq "OK"',
                "column_id": "data_quality_flag",
            },
            "color": "var(--embrapa-green-darker)",
            **base_style,
        },
    ]
    for bad_value in ("MISSING_VALUE", "MISSING_QUANTITY", "INCOMPLETE"):
        rules.append(
            {
                "if": {
                    "filter_query": f'{{data_quality_flag}} eq "{bad_value}"',
                    "column_id": "data_quality_flag",
                },
                "color": "var(--status-error)",
                **base_style,
            }
        )
    return rules


def _prepare_for_table(df: pd.DataFrame, visible: list[str]) -> list[dict]:
    """Convert the filtered DataFrame to a list of dicts for DataTable.

    Keeps numeric columns as raw floats (DataTable formats them client-side
    via the column spec) and renders the few date columns as ISO strings.
    Drops columns not in `visible` to minimize the JSON payload.
    """
    cols = [c for c in visible if c in df.columns]
    out = df[cols].copy()
    if "reference_date" in out.columns:
        out["reference_date"] = out["reference_date"].map(
            lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) else None
        )
    if "last_refresh" in out.columns:
        out["last_refresh"] = out["last_refresh"].map(
            lambda v: v.strftime("%Y-%m-%d %H:%M") if pd.notna(v) else None
        )
    # to_dict preserves NaN as float('nan') which Dash handles fine — empty
    # cell in the rendered table. Lighter than pre-formatting to "—".
    return out.to_dict("records")


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
            years = period_to_years(store.year_range(), period)
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
            records = _prepare_for_table(df.head(MAX_DISPLAY_ROWS), visible)

            table = dash_table.DataTable(
                data=records,
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
                style_data_conditional=_quality_flag_styling(),
            )

            note = None
            if row_count > MAX_DISPLAY_ROWS:
                cap_str = f"{MAX_DISPLAY_ROWS:,}".replace(",", ".")
                note = html.Div(
                    f"Mostrando as primeiras {cap_str} de {row_count_str} linhas. "
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
        years = period_to_years(store.year_range(), period)
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



__all__ = ["PREFIX", "layout", "register_callbacks"]
