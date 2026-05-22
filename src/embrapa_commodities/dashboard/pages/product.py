"""/produto — Análise por produto.

A product picker drives all subsequent panels: value + quantity over time,
top UFs that produce it, and a city ranking table.
"""

from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html

from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    line_with_secondary,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_number,
)

PREFIX = "product"


def _table_style() -> dict:
    return {
        "fontFamily": "Univers, Verdana, Arial, sans-serif",
        "fontSize": "13px",
        "color": "var(--fg-2)",
    }


def _empty_card(message: str) -> html.Div:
    return html.Div(className="empty-state", children=message)


def layout(store: GoldStore) -> html.Div:
    products_df = store.products()
    options = [
        {"label": row.product_description, "value": row.product_code}
        for row in products_df.itertuples(index=False)
    ]
    initial = options[0]["value"] if options else None

    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "Dashboard de Inteligência de Mercado · Commodities",
                                className="overline",
                            ),
                            html.H1("Análise por produto", className="page-title"),
                            html.P(
                                "Selecione um produto para visualizar a série "
                                "histórica de valor, quantidade e dispersão "
                                "geográfica.",
                                className="page-sub",
                            ),
                        ]
                    )
                ],
            ),
            html.Div(
                className="filterbar",
                style={"gridTemplateColumns": "minmax(280px, 360px) 1fr 1fr 1fr"},
                children=[
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Produto"),
                            dcc.Dropdown(
                                id={"section": PREFIX, "control": "product"},
                                options=options,
                                value=initial,
                                clearable=False,
                                searchable=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Convenção monetária"),
                            dcc.RadioItems(
                                id={"section": PREFIX, "control": "conv"},
                                className="seg",
                                options=[
                                    {"label": "IPCA", "value": "ipca"},
                                    {"label": "IGP-M", "value": "igpm"},
                                    {"label": "FX do ano", "value": "yearfx"},
                                ],
                                value="ipca",
                                inline=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Moeda"),
                            dcc.RadioItems(
                                id={"section": PREFIX, "control": "ccy"},
                                className="seg",
                                options=[
                                    {"label": c, "value": c} for c in ("BRL", "USD", "EUR", "CNY")
                                ],
                                value="BRL",
                                inline=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Período"),
                            dcc.RadioItems(
                                id={"section": PREFIX, "control": "period"},
                                className="seg",
                                options=[
                                    {"label": "10a", "value": "10"},
                                    {"label": "20a", "value": "20"},
                                    {"label": "Tudo", "value": "all"},
                                ],
                                value="all",
                                inline=True,
                            ),
                        ],
                    ),
                ],
            ),
            _spinner(html.Div(id={"section": PREFIX, "control": "kpi_strip"}), name="kpi"),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="card",
                        children=[
                            section_header(
                                overline="Série histórica",
                                title="Valor real e quantidade ao longo do tempo",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "ts"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="ts",
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            section_header(
                                overline="Distribuição geográfica",
                                title="UFs que produzem este item",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "ufs"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="ufs",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Detalhamento municipal",
                        title="Top 20 municípios no ano mais recente",
                    ),
                    _spinner(
                        html.Div(
                            id={"section": PREFIX, "control": "cities"},
                            className="table-wrap",
                        ),
                        name="cities",
                    ),
                ],
            ),
        ],
    )


def _spinner(child, *, name: str):
    """Wrap a chart/region in a Dash Loading so users get explicit feedback."""
    return dcc.Loading(
        children=child,
        type="circle",
        color="#006f35",
        parent_className=f"loading-wrap loading-{name}",
        delay_show=120,
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    from dash import no_update

    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "kpi_strip"}, "children"),
        Output({"section": PREFIX, "control": "ts"}, "figure"),
        Output({"section": PREFIX, "control": "ufs"}, "figure"),
        Output({"section": PREFIX, "control": "cities"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "product"}, "value"),
        Input({"section": PREFIX, "control": "conv"}, "value"),
        Input({"section": PREFIX, "control": "ccy"}, "value"),
        Input({"section": PREFIX, "control": "period"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(product_code, conv, ccy, period):
        try:
            conv = conv or "ipca"
            ccy = ccy or "BRL"
            years = _period_to_years(store, period)

            if not product_code:
                empty = _empty_card("Selecione um produto.")
                return empty, _placeholder_fig(), _placeholder_fig(), empty, no_update

            ts = store.time_series(
                convention=conv, currency=ccy, years=years, product_code=product_code
            )
            ts_chart = line_with_secondary(
                ts,
                value_label=f"Valor ({convention_label(conv)}, {ccy})",
                quantity_label="Quantidade",
            )

            hi = ts["reference_year"].max() if not ts.empty else store.year_range()[1]
            ufs = store.top_states(
                year=int(hi), convention=conv, currency=ccy, product_code=product_code
            )
            ufs_chart = bar_top_states(ufs, value_label=f"Valor ({convention_label(conv)}, {ccy})")

            kpis = _kpi_strip(store, product_code, conv, ccy, years)
            cities_table = _cities_table(store, product_code, conv, ccy, int(hi))

            return kpis, ts_chart, ufs_chart, cities_table, no_update
        except Exception as exc:
            err = build_error_payload(
                exc, page="/produto", where="callback de atualização (Produto)"
            )
            return no_update, no_update, no_update, no_update, err


def _placeholder_fig():
    import plotly.graph_objects as go

    from embrapa_commodities.dashboard.components.charts import _empty

    return _empty(go.Figure())


def _period_to_years(store: GoldStore, period: str | None) -> tuple[int, int] | None:
    lo, hi = store.year_range()
    if period == "10":
        return (max(lo, hi - 9), hi)
    if period == "20":
        return (max(lo, hi - 19), hi)
    return None


def _kpi_strip(
    store: GoldStore,
    product_code: str,
    conv: str,
    ccy: str,
    years: tuple[int, int] | None,
) -> html.Div:
    ts = store.time_series(convention=conv, currency=ccy, years=years, product_code=product_code)
    if ts.empty:
        return _empty_card("Sem dados para este produto no recorte selecionado.")
    cum_value = float(ts["value"].sum())
    peak = ts.loc[ts["value"].idxmax()]
    last = ts.iloc[-1]

    # UF dominante
    uf_year = int(last["reference_year"])
    top_uf_df = store.top_states(
        year=uf_year, convention=conv, currency=ccy, product_code=product_code, n=1
    )
    top_uf_label = (
        f"{top_uf_df.iloc[0]['state_name']} ({top_uf_df.iloc[0]['state_acronym']})"
        if not top_uf_df.empty
        else "—"
    )

    # Share atual: this product's value / total all products that year
    all_top = store.top_states(year=uf_year, convention=conv, currency=ccy, n=27)
    total_year = all_top["value"].sum() if not all_top.empty else 0
    product_value_year = float(last["value"])
    share_str = (
        f"{(product_value_year / total_year * 100):.1f}%".replace(".", ",")
        if total_year > 0
        else "—"
    )

    return html.Div(
        className="kpi-row",
        children=[
            kpi_card(
                label=f"Valor acumulado ({convention_label(conv)}) · {ccy}",
                value=fmt_currency(cum_value, ccy),
                sub=f"{int(ts['reference_year'].min())} a {int(ts['reference_year'].max())}",
                spark_values=ts["value"].tail(15).tolist(),
                spark_color="#1D4D7E",
            ),
            kpi_card(
                label="Ano de pico",
                value=str(int(peak["reference_year"])),
                sub=fmt_currency(float(peak["value"]), ccy),
                spark_values=ts["value"].tail(15).tolist(),
                spark_color="#B7791F",
            ),
            kpi_card(
                label="UF dominante",
                value=top_uf_label,
                sub=f"no ano de {uf_year}",
            ),
            kpi_card(
                label=f"Participação em {uf_year}",
                value=share_str,
                sub="do valor extrativo total",
            ),
        ],
    )


def _cities_table(
    store: GoldStore,
    product_code: str,
    conv: str,
    ccy: str,
    year: int,
) -> object:
    df = store.top_cities(year=year, convention=conv, currency=ccy, product_code=product_code, n=20)
    if df.empty:
        return _empty_card("Sem municípios com dados para este produto no ano mais recente.")

    df = df.copy()
    df["value_fmt"] = df["value"].map(lambda v: fmt_currency(float(v), ccy))
    df["qty_fmt"] = df["quantity"].map(lambda v: fmt_number(float(v), decimals=0))

    return dash_table.DataTable(
        data=df[["city_name", "state_acronym", "qty_fmt", "value_fmt"]].to_dict("records"),
        columns=[
            {"name": "Município", "id": "city_name"},
            {"name": "UF", "id": "state_acronym"},
            {"name": "Quantidade", "id": "qty_fmt"},
            {"name": f"Valor ({convention_label(conv)}, {ccy})", "id": "value_fmt"},
        ],
        style_cell={
            "fontFamily": "Univers, Verdana, Arial, sans-serif",
            "fontSize": "13px",
            "padding": "10px 12px",
            "border": "0",
            "borderBottom": "1px solid var(--border-subtle)",
            "backgroundColor": "#fff",
            "color": "var(--fg-2)",
        },
        style_cell_conditional=[
            {
                "if": {"column_id": "qty_fmt"},
                "textAlign": "right",
                "fontFamily": "IBM Plex Mono, monospace",
            },
            {
                "if": {"column_id": "value_fmt"},
                "textAlign": "right",
                "fontFamily": "IBM Plex Mono, monospace",
            },
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
        style_header_conditional=[
            {"if": {"column_id": "qty_fmt"}, "textAlign": "right"},
            {"if": {"column_id": "value_fmt"}, "textAlign": "right"},
        ],
        style_as_list_view=True,
        page_size=20,
    )


__all__ = ["PREFIX", "layout", "register_callbacks"]
