"""/geografia — Análise geográfica.

UF picker, choropleth do Brasil, stacked area of product mix, and a city
ranking when a UF is selected.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import requests
from dash import Input, Output, State, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    choropleth_brazil,
    stacked_product_area,
)
from embrapa_commodities.dashboard.components.export import (
    download_payload,
    export_button,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_number,
)

PREFIX = "geography"

IBGE_GEOJSON_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/estados?formato=application/vnd.geo+json&intrarregiao=UF"
_log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_brazil_geojson() -> dict | None:
    """Fetch the Brazil-by-UF GeoJSON once. Cache forever; fallback to None on failure."""
    try:
        resp = requests.get(IBGE_GEOJSON_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # IBGE returns features keyed by codarea (numeric UF code). We need the
        # 'sigla' (acronym) in properties for our choropleth to match. The API
        # response includes `codarea` only — we attach `sigla` via a static
        # lookup of the 27 UFs.
        for feat in data.get("features", []):
            cod = str(feat["properties"].get("codarea", "")).strip()
            sigla = _CODE_TO_SIGLA.get(cod)
            if sigla:
                feat["properties"]["sigla"] = sigla
        return data
    except Exception as exc:
        _log.warning("Failed to fetch Brazil GeoJSON: %s", exc)
        return None


_CODE_TO_SIGLA = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}


def layout(store: GoldRepository) -> html.Div:
    uf_options = [{"label": "Brasil (todos)", "value": "all"}] + [
        {"label": f"{row.state_name} ({row.state_acronym})", "value": row.state_acronym}
        for row in store.states().itertuples(index=False)
    ]

    lo, hi = store.year_range()

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
                            html.H1(
                                "Análise geográfica",
                                className="page-title",
                            ),
                            html.P(
                                "Distribuição estadual do valor real extrativo, "
                                "evolução temporal do mix de produtos por UF e "
                                "detalhamento municipal.",
                                className="page-sub",
                            ),
                        ]
                    ),
                    html.Div(
                        className="hero-meta",
                        children=html.Div(
                            style={"display": "flex", "gap": "8px"},
                            children=export_button(
                                button_id={"section": PREFIX, "control": "export"},
                                download_id={"section": PREFIX, "control": "download"},
                            ),
                        ),
                    ),
                ],
            ),
            html.Div(
                className="filterbar",
                style={"gridTemplateColumns": "minmax(280px, 360px) 1fr 1fr 1fr"},
                children=[
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Estado (UF)"),
                            dcc.Dropdown(
                                id={"section": PREFIX, "control": "uf"},
                                options=uf_options,
                                value="all",
                                clearable=False,
                                searchable=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Ano de referência"),
                            dcc.Slider(
                                id={"section": PREFIX, "control": "year"},
                                min=lo,
                                max=hi,
                                step=1,
                                value=hi,
                                marks={
                                    int(y): str(int(y))
                                    for y in range(lo, hi + 1, max(1, (hi - lo) // 6))
                                },
                                tooltip={"placement": "bottom"},
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
                                overline="Brasil · valor por UF",
                                title="Mapa de calor estadual",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "choropleth"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="choropleth",
                            ),
                        ],
                    ),
                    html.Div(
                        className="card",
                        children=[
                            section_header(
                                overline="Mix por produto",
                                title="Evolução temporal por produto",
                            ),
                            _spinner(
                                dcc.Graph(
                                    id={"section": PREFIX, "control": "stack"},
                                    config={"displayModeBar": False},
                                    className="chart-box",
                                ),
                                name="stack",
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
                        title="Top 20 municípios do recorte",
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


def register_callbacks(dash_app, store: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "kpi_strip"}, "children"),
        Output({"section": PREFIX, "control": "choropleth"}, "figure"),
        Output({"section": PREFIX, "control": "stack"}, "figure"),
        Output({"section": PREFIX, "control": "cities"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "uf"}, "value"),
        Input({"section": PREFIX, "control": "year"}, "value"),
        Input({"section": PREFIX, "control": "conv"}, "value"),
        Input({"section": PREFIX, "control": "ccy"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(uf, year, conv, ccy):
        try:
            conv = conv or "ipca"
            ccy = ccy or "BRL"
            year = int(year)
            uf_code = None if uf in (None, "all") else uf

            value_label = f"Valor ({convention_label(conv)}, {ccy})"

            # Choropleth always shows all UFs for the selected year.
            states = store.top_states(year=year, convention=conv, currency=ccy, n=27)
            geojson = _load_brazil_geojson() if uf_code is None else None
            if uf_code is not None:
                # When a UF is selected, show its product-mix bar instead.
                mix = store.product_mix(
                    year=year, convention=conv, currency=ccy, state_acronym=uf_code
                )
                mix_renamed = mix.rename(
                    columns={
                        "product_description": "state_name",
                        "product_code": "state_acronym",
                    }
                )
                choro = bar_top_states(mix_renamed, value_label=value_label)
            else:
                choro = choropleth_brazil(states, geojson, value_label=value_label)

            # Stacked area: product mix over time for the recorte.
            stack_df = _build_stacked(store, conv, ccy, uf_code)
            stack = stacked_product_area(stack_df, value_label=value_label)

            kpis = _kpi_strip(store, uf_code, conv, ccy, year)
            cities = _cities_table(store, uf_code, conv, ccy, year)

            return kpis, choro, stack, cities, no_update
        except Exception as exc:
            err = build_error_payload(
                exc, page="/geografia", where="callback de atualização (Geografia)"
            )
            return no_update, no_update, no_update, no_update, err

    @dash_app.callback(
        Output({"section": PREFIX, "control": "download"}, "data"),
        Input({"section": PREFIX, "control": "export"}, "n_clicks"),
        State({"section": PREFIX, "control": "uf"}, "value"),
        State({"section": PREFIX, "control": "year"}, "value"),
        prevent_initial_call=True,
    )
    def _download(n_clicks, uf, year):
        if not n_clicks:
            return no_update
        uf_code = None if uf in (None, "all") else uf
        df = store.filtered(years=(int(year), int(year)), state_acronym=uf_code)
        suffix = uf_code or "brasil"
        return download_payload(df, filename_prefix=f"embrapa-geografia-{suffix}-{int(year)}")


def _build_stacked(store: GoldRepository, conv: str, ccy: str, state_acronym: str | None):
    import pandas as pd

    from embrapa_commodities.dashboard.formatting import value_column

    col = value_column(conv, ccy)
    df = store.filtered(state_acronym=state_acronym)
    if df.empty:
        return pd.DataFrame(columns=["reference_year", "product_description", "value"])
    # Reduce to the top 6 products by lifetime total, then sum the rest into "Outros".
    lifetime = (
        df.groupby(["product_code", "product_description"], as_index=False)
        .agg(total=(col, "sum"))
        .sort_values("total", ascending=False)
    )
    keep = lifetime.head(6)["product_code"].tolist()
    df = df.assign(_grp=df["product_description"].where(df["product_code"].isin(keep), "Outros"))
    grouped = (
        df.groupby(["reference_year", "_grp"], as_index=False)
        .agg(value=(col, "sum"))
        .rename(columns={"_grp": "product_description"})
    )
    return grouped


def _kpi_strip(
    store: GoldRepository,
    state_acronym: str | None,
    conv: str,
    ccy: str,
    year: int,
) -> html.Div:
    states_year = store.top_states(year=year, convention=conv, currency=ccy, n=27)
    if states_year.empty:
        return html.Div(className="empty-state", children="Sem dados para os filtros selecionados.")

    if state_acronym:
        rank_row = states_year[states_year["state_acronym"] == state_acronym]
        if rank_row.empty:
            return html.Div(
                className="empty-state",
                children=f"Sem dados para {state_acronym} em {year}.",
            )
        rank = int(states_year["state_acronym"].tolist().index(state_acronym)) + 1
        value = float(rank_row.iloc[0]["value"])
        share = (value / states_year["value"].sum() * 100) if states_year["value"].sum() else 0
        cov = store.coverage_summary(year=year)
        cities_df = store.top_cities(
            year=year, convention=conv, currency=ccy, state_acronym=state_acronym, n=1_000_000
        )
        n_cities = len(cities_df)
        return html.Div(
            className="kpi-row",
            children=[
                kpi_card(
                    label=f"Valor real ({convention_label(conv)}) · {ccy}",
                    value=fmt_currency(value, ccy),
                    sub=f"em {year}",
                ),
                kpi_card(
                    label="Ranking nacional",
                    value=f"#{rank}",
                    sub=f"entre {cov['states']} UFs com dados",
                ),
                kpi_card(
                    label="Participação nacional",
                    value=f"{share:.1f}%".replace(".", ","),
                    sub="do valor extrativo total",
                ),
                kpi_card(
                    label="Municípios produtores",
                    value=fmt_number(n_cities),
                    sub=f"no estado · {year}",
                ),
            ],
        )

    # Brazil-wide
    total = float(states_year["value"].sum())
    leader = states_year.iloc[0]
    cov = store.coverage_summary(year=year)
    return html.Div(
        className="kpi-row",
        children=[
            kpi_card(
                label=f"Valor real total ({convention_label(conv)}) · {ccy}",
                value=fmt_currency(total, ccy),
                sub=f"Brasil · {year}",
            ),
            kpi_card(
                label="UF líder",
                value=f"{leader['state_name']} ({leader['state_acronym']})",
                sub=fmt_currency(float(leader["value"]), ccy),
            ),
            kpi_card(
                label="UFs com dados",
                value=fmt_number(cov["states"]),
                sub=f"em {year}",
            ),
            kpi_card(
                label="Municípios",
                value=fmt_number(cov["cities"]),
                sub=f"com produção registrada · {year}",
            ),
        ],
    )


def _cities_table(
    store: GoldRepository,
    state_acronym: str | None,
    conv: str,
    ccy: str,
    year: int,
) -> object:
    df = store.top_cities(
        year=year, convention=conv, currency=ccy, state_acronym=state_acronym, n=20
    )
    if df.empty:
        return html.Div(className="empty-state", children="Sem municípios para o recorte.")
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
        style_as_list_view=True,
        page_size=20,
    )


__all__ = ["PREFIX", "layout", "register_callbacks"]
