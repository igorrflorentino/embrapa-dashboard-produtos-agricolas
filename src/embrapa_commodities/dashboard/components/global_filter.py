"""Global Filter Menu for the Dashboard."""

from __future__ import annotations
import json
import dash
from dash import Input, Output, State, dcc, html, MATCH
from dash.exceptions import PreventUpdate
import pandas as pd

from embrapa_commodities.dashboard.data import GoldRepository

_ALL_QUALITY_FLAGS = ["OK", "MISSING_VALUE", "MISSING_QUANTITY", "INCOMPLETE"]
_QUALITY_LABELS = {
    "OK": "Registro completo",
    "MISSING_VALUE": "Valor monetário ausente",
    "MISSING_QUANTITY": "Quantidade ausente",
    "INCOMPLETE": "Registro incompleto",
}

NATIONS = [
    {"label": "Brasil (Produtor)", "value": "BR"},
    {"label": "China (Destino)", "value": "CN", "disabled": True},
    {"label": "Estados Unidos (Destino)", "value": "US", "disabled": True},
    {"label": "União Europeia (Destino)", "value": "EU", "disabled": True},
    {"label": "Argentina (Destino)", "value": "AR", "disabled": True},
]

def make_global_store(repo: GoldRepository) -> dcc.Store:
    lo, hi = repo.year_range()
    return dcc.Store(
        id="global-filters",
        storage_type="session",
        data={
            "commodity": [],
            "start_year": lo,
            "end_year": hi,
            "currency": "BRL",
            "convention": "ipca",
            "quality_flags": _ALL_QUALITY_FLAGS[:],
            "nations": ["BR"],
            "regions": [],
            "states": [],
            "munis": [],
        },
    )

def trigger_bar_layout() -> html.Div:
    return html.Div(
        className="fm-stage",
        children=[
            html.Div(
                className="fm-trigger-bar",
                children=[
                    html.Span("Filtros ativos", className="fm-tb-label"),
                    html.Span(id="fm-trigger-summary", style={"display":"contents"}),
                    html.Span(className="fm-spacer"),
                    html.Button(
                        children=[html.Span("✏️", style={"marginRight": "4px"}), " Editar filtros"],
                        id="fm-open-btn",
                        className="fm-edit-btn",
                        n_clicks=0,
                    ),
                ],
            )
        ]
    )

def _bulk_bar(base_id: str) -> html.Div:
    return html.Div(
        className="fm-bulk compact",
        children=[
            html.Button("Selecionar todos", id={"type": "bulk-all", "id": base_id}),
            html.Span(className="sep-dot"),
            html.Button("Limpar", id={"type": "bulk-none", "id": base_id}),
            html.Span(className="sep-dot"),
            html.Button("Inverter", id={"type": "bulk-inv", "id": base_id}),
        ],
    )

def _search_input(base_id: str, placeholder: str) -> html.Div:
    return html.Div(
        className="fm-search",
        children=[
            html.Span("search", className="fm-search-icn material-symbols-outlined", style={"fontSize": "16px"}),
            dcc.Input(
                id={"type": "search-input", "id": base_id},
                type="text",
                placeholder=placeholder,
                debounce=True,
            )
        ]
    )

def _section_head(num: str, title: str, meta: str | None = None) -> html.Div:
    right_children = []
    if meta:
        right_children.append(html.Span(meta, className="fm-section-meta"))
    return html.Div(
        className="fm-section-head",
        children=[
            html.Div(
                className="fm-section-head-l",
                children=[
                    html.Span(
                        className="fm-section-label",
                        children=[html.Span(num, className="fm-section-num"), f" {title}"]
                    )
                ]
            ),
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "16px"},
                children=right_children
            )
        ]
    )

def modal_layout(repo: GoldRepository) -> html.Div:
    products_df = repo.products()
    commodity_opts = [
        {"label": row.product_description, "value": row.product_code}
        for row in products_df.itertuples(index=False)
    ]
    lo, hi = repo.year_range()
    
    return html.Div(
        id="fm-modal-overlay",
        className="fm-backdrop hidden",
        style={"display": "none"}, # Managed via callback
        children=[
            html.Div(
                className="fm-modal wide",
                children=[
                    html.Header(
                        className="fm-head",
                        children=[
                            html.Div(
                                className="fm-head-text",
                                children=[
                                    html.Span("Inteligência de mercado · Commodities", className="fm-head-over"),
                                    html.Span("Filtros do Dashboard", id="fm-title", className="fm-title"),
                                    html.Span(
                                        children=[
                                            html.Strong("Filtros aplicados"), " sobre gold_commodity_matrix"
                                        ],
                                        className="fm-summary"
                                    )
                                ]
                            ),
                            html.Button("×", id="fm-close-btn", className="fm-close", n_clicks=0),
                        ]
                    ),
                    html.Div(
                        className="fm-body",
                        children=[
                            # 01 Produtos
                            html.Div(
                                className="fm-section",
                                children=[
                                    _section_head("01", "Produtos"),
                                    html.Div(
                                        className="fm-section-inner",
                                        children=[
                                            _search_input("commodity", "Buscar produto..."),
                                            html.Div(
                                                className="fm-grid-scroll",
                                                children=dcc.Checklist(
                                                    id={"type": "checklist", "id": "commodity"},
                                                    options=commodity_opts,
                                                    value=[],
                                                    className="fm-grid",
                                                    labelClassName="fm-check"
                                                )
                                            ),
                                            _bulk_bar("commodity"),
                                            dcc.Store(id={"type": "opts-store", "id": "commodity"}, data=commodity_opts),
                                        ]
                                    )
                                ]
                            ),
                            # 02 Período
                            html.Div(
                                className="fm-section",
                                children=[
                                    _section_head("02", "Período & Conversão Monetária"),
                                    html.Div(
                                        className="fm-row-2",
                                        children=[
                                            html.Div(
                                                className="fm-col",
                                                children=[
                                                    html.Label("Período", className="fm-sub-label"),
                                                    html.Div(
                                                        className="fm-date-row",
                                                        children=[
                                                            html.Div(
                                                                className="fm-date-field",
                                                                children=[
                                                                    html.Label("De"),
                                                                    dcc.Input(id="fm-start-year", type="number", min=lo, max=hi, value=lo, className="fm-date"),
                                                                ]
                                                            ),
                                                            html.Span("→", className="fm-arrow"),
                                                            html.Div(
                                                                className="fm-date-field",
                                                                children=[
                                                                    html.Label("Até"),
                                                                    dcc.Input(id="fm-end-year", type="number", min=lo, max=hi, value=hi, className="fm-date"),
                                                                ]
                                                            )
                                                        ]
                                                    )
                                                ]
                                            ),
                                            html.Div(className="fm-divider"),
                                            html.Div(
                                                className="fm-col",
                                                children=[
                                                    html.Div(
                                                        className="fm-sub",
                                                        children=[
                                                            html.Label("Moeda", className="fm-sub-label"),
                                                            dcc.RadioItems(
                                                                id="fm-currency",
                                                                options=[{"label": c, "value": c} for c in ("BRL", "USD", "EUR", "CNY")],
                                                                value="BRL",
                                                                className="seg",
                                                                labelClassName="seg-opt",
                                                                inline=True
                                                            )
                                                        ]
                                                    ),
                                                    html.Div(
                                                        className="fm-sub",
                                                        children=[
                                                            html.Label("Correção monetária", className="fm-sub-label"),
                                                            dcc.RadioItems(
                                                                id="fm-convention",
                                                                options=[
                                                                    {"label": "IPCA", "value": "ipca"},
                                                                    {"label": "IGP-M", "value": "igpm"},
                                                                    {"label": "IGP-DI", "value": "igpdi"},
                                                                    {"label": "Nominal", "value": "yearfx"},
                                                                ],
                                                                value="ipca",
                                                                className="seg",
                                                                labelClassName="seg-opt",
                                                                inline=True
                                                            )
                                                        ]
                                                    )
                                                ]
                                            )
                                        ]
                                    )
                                ]
                            ),
                            # 03 Geografia
                            html.Div(
                                className="fm-section",
                                children=[
                                    _section_head("03", "Geografia (Seleção em cascata)"),
                                    html.Div(
                                        className="fm-section-inner",
                                        children=[
                                            html.Div(
                                                className="fm-geo-grid",
                                                children=[
                                                    html.Div(
                                                        className="fm-geo-col",
                                                        children=[
                                                            html.Div(className="fm-geo-col-head", children=[html.Span("Nações", className="fm-geo-title"), _bulk_bar("nations")]),
                                                            html.Div(
                                                                className="fm-geo-list",
                                                                children=dcc.Checklist(
                                                                    id={"type": "checklist", "id": "nations"},
                                                                    options=NATIONS,
                                                                    value=["BR"],
                                                                    labelClassName="fm-check geo"
                                                                )
                                                            ),
                                                            dcc.Store(id={"type": "opts-store", "id": "nations"}, data=NATIONS),
                                                        ]
                                                    ),
                                                    html.Div(
                                                        className="fm-geo-col",
                                                        children=[
                                                            html.Div(className="fm-geo-col-head", children=[html.Span("Regiões", className="fm-geo-title"), _bulk_bar("regions")]),
                                                            _search_input("regions", "Buscar região..."),
                                                            html.Div(
                                                                className="fm-geo-list",
                                                                children=dcc.Checklist(
                                                                    id={"type": "checklist", "id": "regions"},
                                                                    labelClassName="fm-check geo"
                                                                )
                                                            ),
                                                            dcc.Store(id={"type": "opts-store", "id": "regions"}, data=[]),
                                                        ]
                                                    ),
                                                    html.Div(
                                                        className="fm-geo-col",
                                                        children=[
                                                            html.Div(className="fm-geo-col-head", children=[html.Span("Estados", className="fm-geo-title"), _bulk_bar("states")]),
                                                            _search_input("states", "Buscar estado..."),
                                                            html.Div(
                                                                className="fm-geo-list",
                                                                children=dcc.Checklist(
                                                                    id={"type": "checklist", "id": "states"},
                                                                    labelClassName="fm-check geo"
                                                                )
                                                            ),
                                                            dcc.Store(id={"type": "opts-store", "id": "states"}, data=[]),
                                                        ]
                                                    ),
                                                    html.Div(
                                                        className="fm-geo-col",
                                                        children=[
                                                            html.Div(className="fm-geo-col-head", children=[html.Span("Municípios", className="fm-geo-title"), _bulk_bar("munis")]),
                                                            _search_input("munis", "Buscar município..."),
                                                            html.Div(
                                                                className="fm-geo-list",
                                                                children=dcc.Checklist(
                                                                    id={"type": "checklist", "id": "munis"},
                                                                    labelClassName="fm-check geo"
                                                                )
                                                            ),
                                                            dcc.Store(id={"type": "opts-store", "id": "munis"}, data=[]),
                                                        ]
                                                    ),
                                                ]
                                            )
                                        ]
                                    )
                                ]
                            ),
                            # 04 Qualidade
                            html.Div(
                                className="fm-section",
                                children=[
                                    _section_head("04", "Confiança dos Dados"),
                                    html.Div(
                                        className="fm-section-inner",
                                        children=[
                                            html.Div(
                                                className="fm-grid-scroll",
                                                children=dcc.Checklist(
                                                    id={"type": "checklist", "id": "quality"},
                                                    options=[{"label": _QUALITY_LABELS[f], "value": f} for f in _ALL_QUALITY_FLAGS],
                                                    value=_ALL_QUALITY_FLAGS[:],
                                                    className="fm-grid",
                                                    labelClassName="fm-check"
                                                )
                                            ),
                                            _bulk_bar("quality"),
                                            dcc.Store(id={"type": "opts-store", "id": "quality"}, data=[{"label": _QUALITY_LABELS[f], "value": f} for f in _ALL_QUALITY_FLAGS]),
                                        ]
                                    )
                                ]
                            )
                        ]
                    ),
                    html.Footer(
                        className="fm-foot",
                        children=[
                            html.Div(
                                className="fm-foot-info",
                                children=[
                                    "Os filtros serão aplicados sobre ",
                                    html.Strong("gold_commodity_matrix"),
                                    html.Span(className="fm-dot"),
                                    "Atualização diária às 06h00 BRT"
                                ]
                            ),
                            html.Button("Restaurar padrão", id="fm-reset-btn", className="btn-ghost", n_clicks=0),
                            html.Button("Cancelar", id="fm-cancel-btn", className="btn-secondary", n_clicks=0),
                            html.Button("Aplicar filtros", id="fm-apply-btn", className="btn-primary", n_clicks=0)
                        ]
                    )
                ]
            )
        ]
    )

def register_callbacks(app: dash.Dash, repo: GoldRepository) -> None:
    # 1. Modal open/close
    @app.callback(
        Output("fm-modal-overlay", "style"),
        Input("fm-open-btn", "n_clicks"),
        Input("fm-close-btn", "n_clicks"),
        Input("fm-cancel-btn", "n_clicks"),
        Input("fm-apply-btn", "n_clicks"),
        State("fm-modal-overlay", "style"),
        prevent_initial_call=True
    )
    def toggle_modal(open_clicks, close_clicks, cancel_clicks, apply_clicks, style):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]["prop_id"].split(".")[0]
        
        style = style or {}
        is_hidden = style.get("display") == "none"
        if trigger == "fm-open-btn":
            if is_hidden:
                new_style = dict(style)
                new_style.pop("display", None)
                return new_style
            return style
        else: # close, cancel or apply
            if not is_hidden:
                new_style = dict(style)
                new_style["display"] = "none"
                return new_style
            return style

    _REGIONS = [
        {"label": "Norte", "value": "Norte"},
        {"label": "Nordeste", "value": "Nordeste"},
        {"label": "Sudeste", "value": "Sudeste"},
        {"label": "Sul", "value": "Sul"},
        {"label": "Centro-Oeste", "value": "Centro-Oeste"},
    ]
    
    _STATES = [
        {"label": "Acre", "value": "AC", "region": "Norte"},
        {"label": "Alagoas", "value": "AL", "region": "Nordeste"},
        {"label": "Amapá", "value": "AP", "region": "Norte"},
        {"label": "Amazonas", "value": "AM", "region": "Norte"},
        {"label": "Bahia", "value": "BA", "region": "Nordeste"},
        {"label": "Ceará", "value": "CE", "region": "Nordeste"},
        {"label": "Distrito Federal", "value": "DF", "region": "Centro-Oeste"},
        {"label": "Espírito Santo", "value": "ES", "region": "Sudeste"},
        {"label": "Goiás", "value": "GO", "region": "Centro-Oeste"},
        {"label": "Maranhão", "value": "MA", "region": "Nordeste"},
        {"label": "Mato Grosso", "value": "MT", "region": "Centro-Oeste"},
        {"label": "Mato Grosso do Sul", "value": "MS", "region": "Centro-Oeste"},
        {"label": "Minas Gerais", "value": "MG", "region": "Sudeste"},
        {"label": "Pará", "value": "PA", "region": "Norte"},
        {"label": "Paraíba", "value": "PB", "region": "Nordeste"},
        {"label": "Paraná", "value": "PR", "region": "Sul"},
        {"label": "Pernambuco", "value": "PE", "region": "Nordeste"},
        {"label": "Piauí", "value": "PI", "region": "Nordeste"},
        {"label": "Rio de Janeiro", "value": "RJ", "region": "Sudeste"},
        {"label": "Rio Grande do Norte", "value": "RN", "region": "Nordeste"},
        {"label": "Rio Grande do Sul", "value": "RS", "region": "Sul"},
        {"label": "Rondônia", "value": "RO", "region": "Norte"},
        {"label": "Roraima", "value": "RR", "region": "Norte"},
        {"label": "Santa Catarina", "value": "SC", "region": "Sul"},
        {"label": "São Paulo", "value": "SP", "region": "Sudeste"},
        {"label": "Sergipe", "value": "SE", "region": "Nordeste"},
        {"label": "Tocantins", "value": "TO", "region": "Norte"},
    ]

    regions_df = repo.regions()
    states_df = repo.states()
    cities_df = repo.cities()

    @app.callback(
        Output({"type": "opts-store", "id": "regions"}, "data"),
        Output({"type": "opts-store", "id": "states"}, "data"),
        Output({"type": "opts-store", "id": "munis"}, "data"),
        Input({"type": "checklist", "id": "regions"}, "value"),
        Input({"type": "checklist", "id": "states"}, "value"),
    )
    def update_geo_opts(sel_regions, sel_states):
        db_regions = set(regions_df["region"].tolist())
        opts_regions = [{"label": r["label"], "value": r["value"], "disabled": r["value"] not in db_regions} for r in _REGIONS]
        
        db_states = set(states_df["state_acronym"].tolist())
        if sel_regions:
            valid_states = [s for s in _STATES if s["region"] in sel_regions]
        else:
            valid_states = _STATES
        opts_states = [{"label": s["label"], "value": s["value"], "disabled": s["value"] not in db_states} for s in valid_states]
        
        filtered_cities = cities_df
        if sel_states:
            filtered_cities = filtered_cities[filtered_cities["state_acronym"].isin(sel_states)]
        if not sel_states and not sel_regions:
             opts_munis = []
        else:
            opts_munis = [{"label": row.city_name, "value": row.city_code} for row in filtered_cities.itertuples()]
        
        return opts_regions, opts_states, opts_munis

    # 3. Search inputs within checklists
    @app.callback(
        Output({"type": "checklist", "id": MATCH}, "options"),
        Input({"type": "search-input", "id": MATCH}, "value"),
        Input({"type": "opts-store", "id": MATCH}, "data"),
    )
    def update_options_with_search(search_val, opts_data):
        if not opts_data:
            return []
        if not search_val:
            return opts_data
        search_lower = search_val.lower()
        return [opt for opt in opts_data if search_lower in str(opt.get("label", "")).lower()]

    # 4. Bulk actions
    @app.callback(
        Output({"type": "checklist", "id": MATCH}, "value", allow_duplicate=True),
        Input({"type": "bulk-all", "id": MATCH}, "n_clicks"),
        Input({"type": "bulk-none", "id": MATCH}, "n_clicks"),
        Input({"type": "bulk-inv", "id": MATCH}, "n_clicks"),
        State({"type": "checklist", "id": MATCH}, "options"),
        State({"type": "checklist", "id": MATCH}, "value"),
        prevent_initial_call=True
    )
    def bulk_action(all_c, none_c, inv_c, current_opts, current_vals):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger_type = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["type"]
        
        all_vals = [opt["value"] for opt in (current_opts or []) if not opt.get("disabled")]
        current_vals = current_vals or []
        
        if trigger_type == "bulk-all":
            return list(set(current_vals + all_vals))
        elif trigger_type == "bulk-none":
            return [v for v in current_vals if v not in all_vals]
        elif trigger_type == "bulk-inv":
            new_vals = [v for v in current_vals if v not in all_vals]
            new_vals += [v for v in all_vals if v not in current_vals]
            return new_vals
        return current_vals

    # 5. Hydrate UI from Global Store (on load)
    @app.callback(
        Output({"type": "checklist", "id": "commodity"}, "value"),
        Output("fm-start-year", "value"),
        Output("fm-end-year", "value"),
        Output("fm-currency", "value"),
        Output("fm-convention", "value"),
        Output({"type": "checklist", "id": "quality"}, "value"),
        Output({"type": "checklist", "id": "nations"}, "value"),
        Output({"type": "checklist", "id": "regions"}, "value"),
        Output({"type": "checklist", "id": "states"}, "value"),
        Output({"type": "checklist", "id": "munis"}, "value"),
        Input("global-filters", "data"),
    )
    def hydrate_ui(data):
        if not data:
            raise PreventUpdate
        return (
            data.get("commodity", []),
            data.get("start_year"),
            data.get("end_year"),
            data.get("currency"),
            data.get("convention"),
            data.get("quality_flags", []),
            data.get("nations", ["BR"]),
            data.get("regions", []),
            data.get("states", []),
            data.get("munis", [])
        )

    # 6. Apply Filters -> Update Global Store
    @app.callback(
        Output("global-filters", "data", allow_duplicate=True),
        Input("fm-apply-btn", "n_clicks"),
        State({"type": "checklist", "id": "commodity"}, "value"),
        State("fm-start-year", "value"),
        State("fm-end-year", "value"),
        State("fm-currency", "value"),
        State("fm-convention", "value"),
        State({"type": "checklist", "id": "quality"}, "value"),
        State({"type": "checklist", "id": "nations"}, "value"),
        State({"type": "checklist", "id": "regions"}, "value"),
        State({"type": "checklist", "id": "states"}, "value"),
        State({"type": "checklist", "id": "munis"}, "value"),
        State("global-filters", "data"),
        prevent_initial_call=True
    )
    def apply_filters(n_clicks, commodity, sy, ey, cur, conv, qual, nat, reg, st, mun, current_data):
        new_data = current_data.copy() if current_data else {}
        new_data.update({
            "commodity": commodity,
            "start_year": sy,
            "end_year": ey,
            "currency": cur,
            "convention": conv,
            "quality_flags": qual,
            "nations": nat,
            "regions": reg,
            "states": st,
            "munis": mun,
        })
        return new_data

    # 7. Update Summary text
    @app.callback(
        Output("fm-trigger-summary", "children"),
        Input("global-filters", "data")
    )
    def update_summary(data):
        if not data:
            return []
        
        pills = []
        c = data.get("commodity", [])
        c_text = f"{len(c)} selecionados" if c else "Todos (12)"
        pills.append(html.Span([html.Span("Produtos", className="fm-chip-k"), f" {c_text}"], className="fm-chip-filter"))
        
        y1, y2 = data.get("start_year"), data.get("end_year")
        y_text = f"{y1}–{y2}" if y1 and y2 else "Todos"
        pills.append(html.Span([html.Span("Período", className="fm-chip-k"), f" {y_text}"], className="fm-chip-filter"))
        
        cur, conv = data.get("currency", "BRL"), data.get("convention", "ipca")
        conv_label = conv.upper() if conv != "yearfx" else "Nominal"
        pills.append(html.Span([html.Span("Moeda", className="fm-chip-k"), f" {cur} · {conv_label}"], className="fm-chip-filter"))
        
        st = data.get("states", [])
        geo_text = f"Brasil · {len(st)} UFs" if st else "Brasil · 27 UFs"
        pills.append(html.Span([html.Span("Geografia", className="fm-chip-k"), f" {geo_text}"], className="fm-chip-filter"))
        
        qual = data.get("quality_flags", [])
        qual_text = f"OK · {len(qual)} selecionadas" if qual else "OK · Estimated"
        pills.append(html.Span([html.Span("Qualidade", className="fm-chip-k"), f" {qual_text}"], className="fm-chip-filter"))
        
        return pills

