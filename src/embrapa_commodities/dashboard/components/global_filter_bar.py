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
    # Period preset matching the legacy filter_bar values.
    "period": "all",  # "10" | "20" | "all"
    "currency": "BRL",  # BRL | USD | EUR | CNY
    # Includes IGP-DI from #17. yearfx = nominal at year-of-record FX (no inflation).
    "convention": "ipca",  # ipca | igpm | igpdi | yearfx
}


def global_filter_store() -> dcc.Store:
    """Mount once at the app shell level — backs all four global filters."""
    return dcc.Store(id=_ID_STORE, storage_type="session", data=DEFAULTS)


def global_filter_bar(repo: GoldRepository) -> html.Div:
    """Render the four global controls. Include in each primary view's layout."""
    products_df = repo.products()
    commodity_opts = [{"label": "Todas as commodities", "value": "all"}] + [
        {"label": row.product_description, "value": row.product_code}
        for row in products_df.itertuples(index=False)
    ]
    return html.Div(
        className="filterbar global-filterbar",
        children=[
            html.Div(
                className="filter",
                children=[
                    html.Label("Commodity"),
                    dcc.Dropdown(
                        id=_ID_COMMODITY,
                        options=commodity_opts,
                        value=DEFAULTS["commodity"],
                        multi=True,
                        clearable=False,
                        searchable=True,
                        placeholder="Selecione uma ou mais",
                    ),
                ],
            ),
            html.Div(
                className="filter",
                children=[
                    html.Label("Período"),
                    dcc.RadioItems(
                        id=_ID_PERIOD,
                        className="seg",
                        options=[
                            {"label": "10a", "value": "10"},
                            {"label": "20a", "value": "20"},
                            {"label": "Tudo", "value": "all"},
                        ],
                        value=DEFAULTS["period"],
                        inline=True,
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
                            {"label": "FX do ano", "value": "yearfx"},
                        ],
                        value=DEFAULTS["convention"],
                        inline=True,
                    ),
                ],
            ),
        ],
    )


def register_callbacks(app) -> None:
    """Register two callbacks: controls → store, and store → controls (hydration).

    The hydration callback is what makes the bar feel "global": every time
    a view re-renders, the controls would normally show DEFAULTS; the
    callback fires on the store's ``modified_timestamp`` and pushes the
    persisted values into the freshly-rendered controls.
    """

    # ── controls → store ─────────────────────────────────────────────────
    @app.callback(
        Output(_ID_STORE, "data"),
        Input(_ID_COMMODITY, "value"),
        Input(_ID_PERIOD, "value"),
        Input(_ID_CURRENCY, "value"),
        Input(_ID_CONVENTION, "value"),
        State(_ID_STORE, "data"),
        prevent_initial_call=True,
    )
    def _write_to_store(commodity, period, currency, convention, existing):
        base = existing or DEFAULTS.copy()
        return {
            "commodity": commodity if commodity else ["all"],
            "period": period or base.get("period", DEFAULTS["period"]),
            "currency": currency or base.get("currency", DEFAULTS["currency"]),
            "convention": convention or base.get("convention", DEFAULTS["convention"]),
        }

    # ── store → controls (hydration on view switch) ──────────────────────
    @app.callback(
        Output(_ID_COMMODITY, "value"),
        Output(_ID_PERIOD, "value"),
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
            data.get("period", DEFAULTS["period"]),
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


def selected_period(store_data: dict | None) -> str:
    return (store_data or DEFAULTS).get("period", DEFAULTS["period"])


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
    "selected_period",
]
