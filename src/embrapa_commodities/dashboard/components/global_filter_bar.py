"""Global filter bar — shared analytical "lens" across the 4 primary views.

Renders four controls (commodity multi-select · period preset · currency ·
monetary correction) whose values persist in a session-scoped
``dcc.Store("global-filters")``. Navigating between Visão Geral, Qualidade
dos Dados, Valor e Volume and Geografia preserves the user's selections —
the filters are part of the analytical session, not part of any one page.

Wiring (done once at app startup):

  1. Mount ``global_filter_store()`` in the app shell — single source of
     truth for the four selected values.
  2. Each view's layout includes ``global_filter_bar(repo)`` — the four
     controls share fixed IDs across views (not pattern-matched), so when
     the user navigates, the new instance of the controls hydrates from
     the store rather than collapsing to defaults.
  3. Call ``register_callbacks(app)`` once at app startup — registers
     bi-directional sync between the controls and the store.

View-local filters (data quality tag, geographic filters in Geografia)
stay per-page; only the four genuinely global filters live here.
"""

from __future__ import annotations

import dash
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from embrapa_commodities.dashboard.data import GoldRepository

# Fixed control IDs (NOT pattern-matched per page). The controls are
# re-instantiated every time a view's layout renders, but they all
# read/write the same store, so analytical state persists across
# navigation.
_ID_STORE = "global-filters"
_ID_COMMODITY = "global-commodity"
_ID_PERIOD = "global-period"
_ID_CURRENCY = "global-currency"
_ID_CONVENTION = "global-convention"

# Initial values surfaced when the store has never been populated (first
# session) and used as fallbacks by the `selected_*` accessors.
DEFAULTS: dict = {
    # Multi-select; the sentinel ``"all"`` (or empty list) means "no commodity filter".
    "commodity": ["all"],
    "start_date": "1986-01-01",
    "end_date": "2024-12-31",
    "data_quality": [], # Empty list means "no data quality filter"
    "currency": "BRL",  # BRL | USD | EUR | CNY
    # Includes IGP-DI from #17. yearfx = nominal at year-of-record FX (no inflation).
    "convention": "ipca",  # ipca | igpm | igpdi | yearfx
}


def global_filter_store() -> dcc.Store:
    """Mount once at the app shell level — backs all four global filters."""
    return dcc.Store(id=_ID_STORE, storage_type="session", data=DEFAULTS)


def global_filter_bar(repo: GoldRepository) -> html.Div:
    """Render the global controls. Include in each primary view's layout."""
    products_df = repo.products()
    commodity_opts = sorted(
        [
            {"label": row.product_description, "value": row.product_code}
            for row in products_df.itertuples(index=False)
        ],
        key=lambda x: x["label"]
    )
    
    # We fetch the available data quality tags
    # Usually we can get them from quality_summary but they are statically known
    quality_opts = [
        {"label": "OK", "value": "OK"},
        {"label": "Falta Valor", "value": "MISSING_VALUE"},
        {"label": "Falta Quantidade", "value": "MISSING_QUANTITY"},
        {"label": "Incompleto", "value": "INCOMPLETE"},
    ]

    return html.Div(
        className="global-filters-container",
        children=[
            # TOP: Commodities Checklist
            html.Div(
                className="checklist-section",
                children=[
                    html.Div(
                        className="checklist-header",
                        children=[
                            html.Label("Cesta de Commodities"),
                            html.Div(
                                className="checklist-buttons",
                                children=[
                                    html.Button("Selecionar Todos", id="btn-com-all", n_clicks=0, className="btn-link"),
                                    html.Button("Desmarcar Todos", id="btn-com-none", n_clicks=0, className="btn-link"),
                                    html.Button("Inverter Seleção", id="btn-com-inv", n_clicks=0, className="btn-link"),
                                ]
                            )
                        ]
                    ),
                    html.Div(
                        className="checklist-scroll-area",
                        children=[
                            dcc.Checklist(
                                id=_ID_COMMODITY,
                                options=commodity_opts,
                                value=DEFAULTS["commodity"],
                                className="multi-column-checklist",
                                labelClassName="checklist-item-label",
                                inputClassName="checklist-item-input"
                            )
                        ]
                    )
                ]
            ),
            
            # MIDDLE: Period, Currency, Correction
            html.Div(
                className="filterbar global-filterbar",
                children=[
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Período"),
                            dcc.DatePickerRange(
                                id=_ID_PERIOD,
                                display_format="MM/YYYY",
                                start_date=DEFAULTS["start_date"],
                                end_date=DEFAULTS["end_date"],
                                min_date_allowed="1986-01-01",
                                max_date_allowed="2030-12-31",
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Moeda"),
                            dcc.RadioItems(
                                id=_ID_CURRENCY,
                                className="seg",
                                options=[{"label": c, "value": c} for c in ("BRL", "USD", "EUR", "CNY")],
                                value=DEFAULTS["currency"],
                                inline=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter",
                        children=[
                            html.Label("Correção monetária"),
                            dcc.RadioItems(
                                id=_ID_CONVENTION,
                                className="seg",
                                options=[
                                    {"label": "IPCA", "value": "ipca"},
                            {"label": "IGP-M", "value": "igpm"},
                            {"label": "IGP-DI", "value": "igpdi"},
                            {"label": "Nominal", "value": "yearfx"},
                        ],
                        value=DEFAULTS["convention"],
                        inline=True,
                    ),
                ],
            ),
            # BOTTOM: Data Quality Checklist
            html.Div(
                className="checklist-section",
                children=[
                    html.Div(
                        className="checklist-header",
                        children=[
                            html.Label("Qualidade dos Dados"),
                            html.Div(
                                className="checklist-buttons",
                                children=[
                                    html.Button("Selecionar Todos", id="btn-dq-all", n_clicks=0, className="btn-link"),
                                    html.Button("Desmarcar Todos", id="btn-dq-none", n_clicks=0, className="btn-link"),
                                    html.Button("Inverter Seleção", id="btn-dq-inv", n_clicks=0, className="btn-link"),
                                ]
                            )
                        ]
                    ),
                    html.Div(
                        className="checklist-scroll-area quality-scroll-area",
                        children=[
                            dcc.Checklist(
                                id="global-data-quality",
                                options=quality_opts,
                                value=DEFAULTS["data_quality"],
                                className="multi-column-checklist",
                                labelClassName="checklist-item-label",
                                inputClassName="checklist-item-input"
                            )
                        ]
                    )
                ]
            )
        ],
    )


def register_callbacks(app) -> None:
    """Register two callbacks: controls → store, and store → controls (hydration).

    The hydration callback is what makes the bar feel "global": every time
    a view re-renders, the controls would normally show DEFAULTS; the
    callback fires on the store's ``modified_timestamp`` and pushes the
    persisted values into the freshly-rendered controls.
    """

    @app.callback(
        Output(_ID_COMMODITY, "value", allow_duplicate=True),
        Input("btn-com-all", "n_clicks"),
        Input("btn-com-none", "n_clicks"),
        Input("btn-com-inv", "n_clicks"),
        State(_ID_COMMODITY, "options"),
        State(_ID_COMMODITY, "value"),
        prevent_initial_call=True
    )
    def update_commodity_checklist(all_clicks, none_clicks, inv_clicks, options, current_value):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        all_values = [opt["value"] for opt in options]
        current = current_value or []
        if "all" in current:
            current = []
            
        if button_id == "btn-com-all":
            return all_values
        elif button_id == "btn-com-none":
            return []
        elif button_id == "btn-com-inv":
            return [v for v in all_values if v not in current]
        raise PreventUpdate

    @app.callback(
        Output("global-data-quality", "value", allow_duplicate=True),
        Input("btn-dq-all", "n_clicks"),
        Input("btn-dq-none", "n_clicks"),
        Input("btn-dq-inv", "n_clicks"),
        State("global-data-quality", "options"),
        State("global-data-quality", "value"),
        prevent_initial_call=True
    )
    def update_quality_checklist(all_clicks, none_clicks, inv_clicks, options, current_value):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        all_values = [opt["value"] for opt in options]
        current = current_value or []
        
        if button_id == "btn-dq-all":
            return all_values
        elif button_id == "btn-dq-none":
            return []
        elif button_id == "btn-dq-inv":
            return [v for v in all_values if v not in current]
        raise PreventUpdate


    # ── controls → store ─────────────────────────────────────────────────
    @app.callback(
        Output(_ID_STORE, "data"),
        Input(_ID_COMMODITY, "value"),
        Input(_ID_PERIOD, "start_date"),
        Input(_ID_PERIOD, "end_date"),
        Input("global-data-quality", "value"),
        Input(_ID_CURRENCY, "value"),
        Input(_ID_CONVENTION, "value"),
        State(_ID_STORE, "data"),
        prevent_initial_call=True,
    )
    def _write_to_store(commodity, start_date, end_date, data_quality, currency, convention, existing):
        base = existing or DEFAULTS.copy()
        return {
            "commodity": commodity if commodity else ["all"],
            "start_date": start_date or base.get("start_date", DEFAULTS["start_date"]),
            "end_date": end_date or base.get("end_date", DEFAULTS["end_date"]),
            "data_quality": data_quality or [],
            "currency": currency or base.get("currency", DEFAULTS["currency"]),
            "convention": convention or base.get("convention", DEFAULTS["convention"]),
        }

    # ── store → controls (hydration on view switch) ──────────────────────
    @app.callback(
        Output(_ID_COMMODITY, "value"),
        Output(_ID_PERIOD, "start_date"),
        Output(_ID_PERIOD, "end_date"),
        Output("global-data-quality", "value"),
        Output(_ID_CURRENCY, "value"),
        Output(_ID_CONVENTION, "value"),
        Input(_ID_STORE, "modified_timestamp"),
        State(_ID_STORE, "data"),
        prevent_initial_call=False,
    )
    def _hydrate_from_store(_ts, data):
        if not data:
            raise PreventUpdate
        return (
            data.get("commodity", DEFAULTS["commodity"]),
            data.get("start_date", DEFAULTS["start_date"]),
            data.get("end_date", DEFAULTS["end_date"]),
            data.get("data_quality", DEFAULTS["data_quality"]),
            data.get("currency", DEFAULTS["currency"]),
            data.get("convention", DEFAULTS["convention"]),
        )


# ── Accessors for page callbacks ─────────────────────────────────────────
# Page callbacks should read the store directly via `Input("global-filters",
# "data")` and pass the result to these helpers — keeps decoding semantics
# in one place.


def selected_commodity_codes(store_data: dict | None) -> list[str] | None:
    """Return list of selected ``product_code`` strings, or ``None`` if "all" is selected.

    ``None`` is the signal the data layer uses for "no commodity filter".
    """
    codes = (store_data or DEFAULTS).get("commodity") or ["all"]
    if not codes or "all" in codes:
        return None
    filtered = [c for c in codes if c and c != "all"]
    return filtered or None


def selected_period_years(store_data: dict | None) -> tuple[int, int]:
    """Returns the (start_year, end_year) derived from start_date and end_date."""
    data = store_data or DEFAULTS
    sd = data.get("start_date", DEFAULTS["start_date"])
    ed = data.get("end_date", DEFAULTS["end_date"])
    try:
        start_year = int(sd.split("-")[0])
        end_year = int(ed.split("-")[0])
        return (start_year, end_year)
    except (ValueError, AttributeError):
        return (1986, 2024)


def selected_data_quality(store_data: dict | None) -> list[str] | None:
    """Returns the selected data quality tags, or None if no filter is applied."""
    data = store_data or DEFAULTS
    tags = data.get("data_quality", [])
    if not tags:
        return None
    return tags


def selected_currency(store_data: dict | None) -> str:
    return (store_data or DEFAULTS).get("currency", DEFAULTS["currency"])


def selected_convention(store_data: dict | None) -> str:
    return (store_data or DEFAULTS).get("convention", DEFAULTS["convention"])


__all__ = [
    "DEFAULTS",
    "global_filter_bar",
    "global_filter_store",
    "register_callbacks",
    "selected_commodity_codes",
    "selected_convention",
    "selected_currency",
    "selected_data_quality",
    "selected_period_years",
]
