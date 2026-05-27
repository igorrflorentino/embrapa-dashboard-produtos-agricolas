"""Filter bar — Período / Produto / UF / Convenção / Moeda / Apenas OK.

This is a *pure-layout* helper. Each page wires its own callback to its own
`Store` and the controls' IDs are namespaced via a `prefix` argument so we
can mount more than one filterbar in the app without clashing.
"""

from __future__ import annotations

from dash import dcc, html

from embrapa_commodities.dashboard.data import GoldRepository


def _id(prefix: str, name: str) -> dict[str, str]:
    return {"section": prefix, "control": name}


def filter_bar(prefix: str, store: GoldRepository, *, show_uf: bool = True) -> html.Div:
    """Render the filter row.

    `prefix` namespaces the dcc IDs (e.g. `"overview"` → `{"section":"overview","control":"conv"}`).
    """
    products_df = store.products()
    product_opts = [{"label": "Todos os produtos", "value": "all"}] + [
        {"label": row.product_description, "value": row.product_code}
        for row in products_df.itertuples(index=False)
    ]

    states_df = store.states()
    uf_opts = [{"label": "Todos os estados", "value": "all"}] + [
        {"label": f"{row.state_name} ({row.state_acronym})", "value": row.state_acronym}
        for row in states_df.itertuples(index=False)
    ]

    return html.Div(
        className="filterbar",
        children=[
            html.Div(
                className="filter",
                children=[
                    html.Label("Período"),
                    dcc.RadioItems(
                        id=_id(prefix, "period"),
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
            html.Div(
                className="filter",
                children=[
                    html.Label("Produto"),
                    dcc.Dropdown(
                        id=_id(prefix, "product"),
                        options=product_opts,
                        value="all",
                        clearable=False,
                        searchable=True,
                    ),
                ],
            ),
            html.Div(
                className="filter",
                children=[
                    html.Label("Estado (UF)"),
                    dcc.Dropdown(
                        id=_id(prefix, "uf"),
                        options=uf_opts,
                        value="all",
                        clearable=False,
                        searchable=True,
                    ),
                ]
                if show_uf
                else [],
                style={} if show_uf else {"visibility": "hidden"},
            ),
            html.Div(
                className="filter",
                children=[
                    html.Label("Convenção monetária"),
                    dcc.RadioItems(
                        id=_id(prefix, "conv"),
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
                        id=_id(prefix, "ccy"),
                        className="seg",
                        options=[{"label": c, "value": c} for c in ("BRL", "USD", "EUR", "CNY")],
                        value="BRL",
                        inline=True,
                    ),
                ],
            ),
            html.Div(
                className="filter check-inline",
                children=[
                    html.Label(
                        className="checkbox-row",
                        children=[
                            dcc.Checklist(
                                id=_id(prefix, "only_ok"),
                                options=[{"label": "", "value": "ok"}],
                                value=["ok"],
                                inline=True,
                                style={"display": "inline"},
                            ),
                            html.Span(
                                [
                                    "Apenas ",
                                    html.Code("data_quality_flag = OK", className="mono"),
                                ]
                            ),
                        ],
                    )
                ],
            ),
        ],
    )
