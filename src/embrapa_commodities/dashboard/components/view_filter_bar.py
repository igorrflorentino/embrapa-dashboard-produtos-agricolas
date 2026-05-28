"""Per-view filter bar — each primary view carries its own analytical lens.

Design mirrors the Embrapa Commodities Design System FM sections: numbered
section cards with a green left-rail header, scrollable checkbox grids, and
segmented controls for single-choice dimensions.

Dimensions that don't apply to a given view are rendered as a disabled
placeholder — consistent layout, clear "não se aplica" label — matching the
design-system requirement for UX consistency across views.

Usage pattern per view
----------------------
1. Add ``make_store(PREFIX, repo)`` to the view's ``layout()`` return value.
2. Call ``make_filter_bar(PREFIX, repo, ...)`` in ``layout()``.
3. Call ``register_view_callbacks(app, PREFIX, ...)`` inside the view's own
   ``register_callbacks(app, repo)`` — before registering chart callbacks.
4. In page chart callbacks, use ``Input("{PREFIX}-filters", "data")`` and
   pass the data dict to the accessor helpers below.
"""

from __future__ import annotations

import dash
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from embrapa_commodities.dashboard.data import GoldRepository

_ALL_QUALITY_FLAGS = ["OK", "MISSING_VALUE", "MISSING_QUANTITY", "INCOMPLETE"]
_QUALITY_LABELS = {
    "OK": "Registro completo",
    "MISSING_VALUE": "Valor monetário ausente",
    "MISSING_QUANTITY": "Quantidade ausente",
    "INCOMPLETE": "Registro incompleto",
}


def make_store(prefix: str, repo: GoldRepository) -> dcc.Store:
    """Session-scoped store initialised with the actual year range from the DB."""
    lo, hi = repo.year_range()
    return dcc.Store(
        id=f"{prefix}-filters",
        storage_type="session",
        data={
            "commodity": [],
            "start_year": lo,
            "end_year": hi,
            "currency": "BRL",
            "convention": "ipca",
            "quality_flags": _ALL_QUALITY_FLAGS[:],
            "states": [],
        },
    )


# ── Layout helpers ────────────────────────────────────────────────────────────


def _section_head(number: int, title: str, extras: list | None = None) -> html.Div:
    return html.Div(
        className="vf-section-head",
        children=[
            html.Div(
                className="vf-section-head-l",
                children=html.Span(
                    className="vf-section-label",
                    children=[html.Span(str(number), className="vf-section-num"), title],
                ),
            ),
            *(extras or []),
        ],
    )


def _bulk_bar(prefix: str, base: str) -> html.Div:
    return html.Div(
        className="vf-bulk",
        children=[
            html.Button(
                "Selecionar todos", id=f"{prefix}-{base}-all", n_clicks=0, className="vf-bulk-btn"
            ),
            html.Span(className="vf-sep-dot"),
            html.Button(
                "Desmarcar", id=f"{prefix}-{base}-none", n_clicks=0, className="vf-bulk-btn"
            ),
            html.Span(className="vf-sep-dot"),
            html.Button("Inverter", id=f"{prefix}-{base}-inv", n_clicks=0, className="vf-bulk-btn"),
        ],
    )


def _na_section(number: int, title: str, reason: str) -> html.Div:
    return html.Div(
        className="vf-section vf-section-na",
        children=[
            html.Div(
                className="vf-section-head",
                children=[
                    html.Div(
                        className="vf-section-head-l",
                        children=html.Span(
                            className="vf-section-label",
                            children=[html.Span(str(number), className="vf-section-num"), title],
                        ),
                    ),
                    html.Span("não se aplica", className="vf-na-badge"),
                ],
            ),
            html.Div(
                className="vf-section-inner", children=html.P(reason, className="vf-na-reason")
            ),
        ],
    )


def make_filter_bar(
    prefix: str,
    repo: GoldRepository,
    *,
    has_currency: bool = True,
    has_quality: bool = False,
    has_states: bool = False,
) -> html.Div:
    """Build the inline filter panel for a given view."""
    products_df = repo.products()
    commodity_opts = sorted(
        [
            {"label": row.product_description, "value": row.product_code}
            for row in products_df.itertuples(index=False)
        ],
        key=lambda x: x["label"],
    )
    lo, hi = repo.year_range()

    sec = 1
    sections: list = []

    # ── Section 1: Cesta de Commodities ──────────────────────────────────────
    sections.append(
        html.Div(
            className="vf-section",
            children=[
                _section_head(sec, "Cesta de commodities", [_bulk_bar(prefix, "com")]),
                html.Div(
                    className="vf-section-inner",
                    children=html.Div(
                        className="vf-grid-scroll",
                        children=dcc.Checklist(
                            id=f"{prefix}-commodity",
                            options=commodity_opts,
                            value=[o["value"] for o in commodity_opts],
                            className="vf-grid",
                            labelClassName="vf-check",
                            inputClassName="vf-check-input",
                        ),
                    ),
                ),
            ],
        )
    )
    sec += 1

    # ── Section 2: Período + Financeiro ──────────────────────────────────────
    period_col = html.Div(
        className="vf-col",
        children=[
            html.Span("Período", className="vf-sub-label"),
            html.Div(
                className="vf-date-row",
                children=[
                    html.Div(
                        className="vf-date-field",
                        children=[
                            html.Label("De", className="vf-date-label"),
                            dcc.Input(
                                id=f"{prefix}-start-year",
                                type="number",
                                value=lo,
                                min=lo,
                                max=hi,
                                step=1,
                                debounce=True,
                                className="vf-date-input",
                            ),
                        ],
                    ),
                    html.Span("→", className="vf-arrow"),
                    html.Div(
                        className="vf-date-field",
                        children=[
                            html.Label("Até", className="vf-date-label"),
                            dcc.Input(
                                id=f"{prefix}-end-year",
                                type="number",
                                value=hi,
                                min=lo,
                                max=hi,
                                step=1,
                                debounce=True,
                                className="vf-date-input",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    if has_currency:
        financial_col = html.Div(
            className="vf-col",
            children=[
                html.Span("Financeiro", className="vf-sub-label"),
                html.Div(
                    className="vf-sub",
                    children=[
                        html.Span("Moeda", className="vf-sub-label-sm"),
                        dcc.RadioItems(
                            id=f"{prefix}-currency",
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
                    className="vf-sub",
                    children=[
                        html.Span("Correção monetária", className="vf-sub-label-sm"),
                        dcc.RadioItems(
                            id=f"{prefix}-convention",
                            className="seg",
                            options=[
                                {"label": "IPCA", "value": "ipca"},
                                {"label": "IGP-M", "value": "igpm"},
                                {"label": "IGP-DI", "value": "igpdi"},
                                {"label": "Nominal", "value": "yearfx"},
                            ],
                            value="ipca",
                            inline=True,
                        ),
                    ],
                ),
            ],
        )
    else:
        financial_col = html.Div(
            className="vf-col vf-col-na",
            children=[
                html.Div(
                    children=[
                        html.Span("Financeiro", className="vf-sub-label"),
                        html.Span("não se aplica", className="vf-na-badge"),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "10px"},
                ),
                html.P(
                    "Moeda e correção monetária não se aplicam — "
                    "esta view analisa integridade estrutural, não valores monetários.",
                    className="vf-na-reason",
                ),
            ],
        )

    sections.append(
        html.Div(
            className="vf-section",
            children=[
                _section_head(sec, "Período e financeiro"),
                html.Div(
                    className="vf-row-2",
                    children=[period_col, html.Div(className="vf-divider"), financial_col],
                ),
            ],
        )
    )
    sec += 1

    # ── Section 3: Flag de qualidade (or N/A) ─────────────────────────────────
    if has_quality:
        quality_opts = [{"label": _QUALITY_LABELS[f], "value": f} for f in _ALL_QUALITY_FLAGS]
        sections.append(
            html.Div(
                className="vf-section",
                children=[
                    _section_head(
                        sec,
                        "Flag de qualidade",
                        [
                            html.Div(
                                className="vf-bulk",
                                children=[
                                    html.Button(
                                        "Todos",
                                        id=f"{prefix}-dq-all",
                                        n_clicks=0,
                                        className="vf-bulk-btn",
                                    ),
                                    html.Span(className="vf-sep-dot"),
                                    html.Button(
                                        "Nenhum",
                                        id=f"{prefix}-dq-none",
                                        n_clicks=0,
                                        className="vf-bulk-btn",
                                    ),
                                ],
                            )
                        ],
                    ),
                    html.Div(
                        className="vf-section-inner",
                        children=dcc.Checklist(
                            id=f"{prefix}-quality-flags",
                            options=quality_opts,
                            value=_ALL_QUALITY_FLAGS[:],
                            className="vf-grid vf-grid-4",
                            labelClassName="vf-check",
                            inputClassName="vf-check-input",
                        ),
                    ),
                ],
            )
        )
        sec += 1
    else:
        sections.append(
            _na_section(
                sec,
                "Flag de qualidade",
                "Esta view usa apenas registros com data_quality_flag = OK.",
            )
        )
        sec += 1

    # ── Section 4 (Geography only): Estados / UF ─────────────────────────────
    if has_states:
        states_df = repo.states()
        state_opts = [
            {"label": f"{row.state_acronym} — {row.state_name}", "value": row.state_acronym}
            for row in states_df.itertuples(index=False)
        ]
        sections.append(
            html.Div(
                className="vf-section",
                children=[
                    _section_head(sec, "Estados / UF", [_bulk_bar(prefix, "st")]),
                    html.Div(
                        className="vf-section-inner",
                        children=html.Div(
                            className="vf-grid-scroll",
                            children=dcc.Checklist(
                                id=f"{prefix}-states",
                                options=state_opts,
                                value=[o["value"] for o in state_opts],
                                className="vf-grid",
                                labelClassName="vf-check",
                                inputClassName="vf-check-input",
                            ),
                        ),
                    ),
                ],
            )
        )

    return html.Div(className="vf-card", children=sections)


# ── Callback registration ──────────────────────────────────────────────────────


def register_view_callbacks(
    app,
    prefix: str,
    *,
    has_currency: bool = True,
    has_quality: bool = False,
    has_states: bool = False,
) -> None:
    """Register bulk-action and store-sync callbacks for the given view prefix."""

    # Commodity bulk actions
    @app.callback(
        Output(f"{prefix}-commodity", "value", allow_duplicate=True),
        Input(f"{prefix}-com-all", "n_clicks"),
        Input(f"{prefix}-com-none", "n_clicks"),
        Input(f"{prefix}-com-inv", "n_clicks"),
        State(f"{prefix}-commodity", "options"),
        State(f"{prefix}-commodity", "value"),
        prevent_initial_call=True,
    )
    def _com_bulk(all_n, none_n, inv_n, opts, cur):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        btn = ctx.triggered[0]["prop_id"].split(".")[0]
        all_vals = [o["value"] for o in (opts or [])]
        cur = cur or []
        if btn == f"{prefix}-com-all":
            return all_vals
        if btn == f"{prefix}-com-none":
            return []
        return [v for v in all_vals if v not in cur]

    if has_quality:

        @app.callback(
            Output(f"{prefix}-quality-flags", "value", allow_duplicate=True),
            Input(f"{prefix}-dq-all", "n_clicks"),
            Input(f"{prefix}-dq-none", "n_clicks"),
            State(f"{prefix}-quality-flags", "options"),
            prevent_initial_call=True,
        )
        def _dq_bulk(all_n, none_n, opts):
            ctx = dash.callback_context
            if not ctx.triggered:
                raise PreventUpdate
            btn = ctx.triggered[0]["prop_id"].split(".")[0]
            all_vals = [o["value"] for o in (opts or [])]
            return all_vals if btn == f"{prefix}-dq-all" else []

    if has_states:

        @app.callback(
            Output(f"{prefix}-states", "value", allow_duplicate=True),
            Input(f"{prefix}-st-all", "n_clicks"),
            Input(f"{prefix}-st-none", "n_clicks"),
            Input(f"{prefix}-st-inv", "n_clicks"),
            State(f"{prefix}-states", "options"),
            State(f"{prefix}-states", "value"),
            prevent_initial_call=True,
        )
        def _st_bulk(all_n, none_n, inv_n, opts, cur):
            ctx = dash.callback_context
            if not ctx.triggered:
                raise PreventUpdate
            btn = ctx.triggered[0]["prop_id"].split(".")[0]
            all_vals = [o["value"] for o in (opts or [])]
            cur = cur or []
            if btn == f"{prefix}-st-all":
                return all_vals
            if btn == f"{prefix}-st-none":
                return []
            return [v for v in all_vals if v not in cur]

    # Build controls → store callback inputs dynamically
    write_inputs: list = [
        Input(f"{prefix}-commodity", "value"),
        Input(f"{prefix}-start-year", "value"),
        Input(f"{prefix}-end-year", "value"),
    ]
    if has_currency:
        write_inputs += [
            Input(f"{prefix}-currency", "value"),
            Input(f"{prefix}-convention", "value"),
        ]
    if has_quality:
        write_inputs.append(Input(f"{prefix}-quality-flags", "value"))
    if has_states:
        write_inputs.append(Input(f"{prefix}-states", "value"))

    def _write(*args):
        it = iter(args)
        commodity = next(it) or []
        start_year = int(next(it) or 1986)
        end_year = int(next(it) or 2024)
        currency = next(it) if has_currency else "BRL"
        convention = next(it) if has_currency else "ipca"
        quality_flags = next(it) if has_quality else _ALL_QUALITY_FLAGS[:]
        states = next(it) if has_states else []
        return {
            "commodity": commodity,
            "start_year": start_year,
            "end_year": end_year,
            "currency": currency or "BRL",
            "convention": convention or "ipca",
            "quality_flags": quality_flags or _ALL_QUALITY_FLAGS[:],
            "states": states or [],
        }

    app.callback(
        Output(f"{prefix}-filters", "data"),
        *write_inputs,
        prevent_initial_call=True,
    )(_write)

    # Build store → controls hydration callback outputs dynamically
    hydrate_outputs: list = [
        Output(f"{prefix}-commodity", "value"),
        Output(f"{prefix}-start-year", "value"),
        Output(f"{prefix}-end-year", "value"),
    ]
    if has_currency:
        hydrate_outputs += [
            Output(f"{prefix}-currency", "value"),
            Output(f"{prefix}-convention", "value"),
        ]
    if has_quality:
        hydrate_outputs.append(Output(f"{prefix}-quality-flags", "value"))
    if has_states:
        hydrate_outputs.append(Output(f"{prefix}-states", "value"))

    def _hydrate(_ts, data):
        if not data:
            raise PreventUpdate
        result = [
            data.get("commodity", []),
            data.get("start_year", 1986),
            data.get("end_year", 2024),
        ]
        if has_currency:
            result += [data.get("currency", "BRL"), data.get("convention", "ipca")]
        if has_quality:
            result.append(data.get("quality_flags", _ALL_QUALITY_FLAGS[:]))
        if has_states:
            result.append(data.get("states", []))
        return tuple(result)

    app.callback(
        *hydrate_outputs,
        Input(f"{prefix}-filters", "modified_timestamp"),
        State(f"{prefix}-filters", "data"),
        prevent_initial_call=False,
    )(_hydrate)


# ── Accessor helpers ───────────────────────────────────────────────────────────


def get_commodity_codes(data: dict | None) -> list[str] | None:
    """Returns selected product_code list, or None (= no filter = all)."""
    codes = (data or {}).get("commodity") or []
    return codes if codes else None


def get_period_years(data: dict | None) -> tuple[int, int]:
    d = data or {}
    return int(d.get("start_year", 1986)), int(d.get("end_year", 2024))


def get_currency(data: dict | None) -> str:
    return (data or {}).get("currency", "BRL")


def get_convention(data: dict | None) -> str:
    return (data or {}).get("convention", "ipca")


def get_quality_flags(data: dict | None) -> list[str]:
    flags = (data or {}).get("quality_flags") or []
    return flags if flags else _ALL_QUALITY_FLAGS[:]


def get_states(data: dict | None) -> list[str] | None:
    states = (data or {}).get("states") or []
    return states if states else None


__all__ = [
    "get_commodity_codes",
    "get_convention",
    "get_currency",
    "get_period_years",
    "get_quality_flags",
    "get_states",
    "make_filter_bar",
    "make_store",
    "register_view_callbacks",
]
