"""/ibge-pevs/valor-e-volume — Valor e Volume.

Eixo tempo × produto × métricas monetárias e de volume. Sem dimensão
geográfica — para isso, abra a view Geografia.
Filtros são gerenciados globalmente.
"""

from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    line_time_series,
    line_with_secondary,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_number,
)

PREFIX = "valor-volume"


def _hero() -> html.Div:
    return html.Div(
        className="page-hero",
        children=[
            html.Div(
                children=[
                    html.Div(
                        "Dashboard de Inteligência de Mercado · Commodities",
                        className="overline",
                    ),
                    html.H1("Valor e Volume", className="page-title"),
                    html.P(
                        "Evolução temporal de quantidade física e valor monetário das "
                        "commodities selecionadas, sob diferentes convenções de correção "
                        "(IPCA / IGP-M / IGP-DI) e moedas. Sem dimensão geográfica — "
                        "para isso, abra a view Geografia.",
                        className="page-sub",
                    ),
                ]
            ),
        ],
    )


def layout(repo: GoldRepository) -> html.Div:
    return html.Div(
        className="screen",
        children=[
            _hero(),
            html.Div(id={"section": PREFIX, "control": "kpi-row"}, className="kpi-row"),
            section_header(overline="Tendências", title="Valor e volume ao longo do tempo"),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "value-line"},
                            config={"displayModeBar": False},
                        ),
                    ),
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "volume-line"},
                            config={"displayModeBar": False},
                        ),
                    ),
                ],
            ),
            section_header(overline="Ranking", title="Commodities por valor no último ano"),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "ranking"},
                    config={"displayModeBar": False},
                ),
            ),
            section_header(
                overline="Tabela de ranking",
                title="Commodities por valor e volume — período selecionado",
            ),
            html.Div(
                className="card",
                children=html.Div(id={"section": PREFIX, "control": "ranking-table"}),
            ),
            about_data_panel(
                sources=[
                    "**`gold_commodity_matrix`** — matriz unificada, agregação (ano, commodity) "
                    "feita dinamicamente."
                ],
                coverage_notes=[
                    "Valor médio por unidade física é proxy de preço; **não compare entre "
                    "commodities** porque mistura unidades (t / m³)."
                ],
                caveats=[
                    "`val_yearfx_*` em USD/EUR/CNY é NULL pré-1994. Quando o filtro de período "
                    "inclui anos sem dado para a combinação convenção × moeda, a linha aparece "
                    "cortada — isso não é bug, é cobertura real da fonte.",
                ],
            ),
        ],
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────


def _build_kpis(
    repo: GoldRepository,
    *,
    filters: dict,
) -> list:
    series = repo.time_series(filters=filters)
    if series.empty:
        return [html.Div("Sem dados.", className="empty-state")]
    total_value = float(series["value"].sum() or 0.0)
    total_qty = float(series["quantity"].sum() or 0.0)
    avg_unit = (total_value / total_qty) if total_qty else None
    n_years = len(series)
    
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    commodities = filters.get("commodity", [])
    
    return [
        kpi_card(
            label=f"Valor agregado · {convention_label(conv)} · {ccy}",
            value=fmt_currency(total_value, ccy),
            sub=f"{n_years} ano(s) no recorte",
        ),
        kpi_card(
            label="Volume agregado (toneladas/m³)",
            value=fmt_number(total_qty, decimals=0),
            sub="unidade dominante por commodity",
        ),
        kpi_card(
            label="Valor médio por unidade física",
            value=fmt_currency(avg_unit, ccy) if avg_unit is not None else "—",
            sub="proxy de preço — distorcido em cestas",
        ),
        kpi_card(
            label="Commodities no recorte",
            value=str(len(commodities)) if commodities else "todas",
            sub="sem filtro"
            if not commodities
            else ", ".join(commodities[:3]) + ("…" if len(commodities) > 3 else ""),
        ),
    ]


def _ranking_table(
    repo: GoldRepository,
    *,
    filters: dict,
) -> html.Div:
    df = repo.product_mix(filters=filters, top_n=20)
    
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    year = filters.get("end_year", 2024)
    
    if df.empty:
        return html.Div("Sem dados para os filtros selecionados.", className="empty-state")
    cols = [c for c in ["product_description", "value", "share"] if c in df.columns]
    value_label = f"Valor ({ccy}, {convention_label(conv)}) — {year}"
    col_labels = {
        "product_description": "Commodity",
        "value": value_label,
        "share": "Share (%)",
    }
    return dash_table.DataTable(
        data=df[cols].to_dict("records"),
        columns=[
            {
                "name": col_labels.get(c, c),
                "id": c,
                "type": "numeric" if c != "product_description" else "text",
            }
            for c in cols
        ],
        page_size=20,
        sort_action="native",
        style_as_list_view=True,
        style_cell={"fontFamily": "Univers, Arial, sans-serif", "fontSize": "13px"},
        style_data_conditional=[
            {
                "if": {"column_id": "share"},
                "fontFamily": "var(--font-mono)",
                "color": "var(--embrapa-green-darker)",
            },
        ],
        style_header={
            "fontFamily": "Univers, Arial, sans-serif",
            "fontSize": "11px",
            "textTransform": "uppercase",
            "letterSpacing": "0.08em",
            "color": "#888",
            "fontWeight": "500",
        },
    )


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "value-line"}, "figure"),
        Output({"section": PREFIX, "control": "volume-line"}, "figure"),
        Output({"section": PREFIX, "control": "ranking"}, "figure"),
        Output({"section": PREFIX, "control": "ranking-table"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input("global-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(filters):
        try:
            if not filters:
                return no_update, no_update, no_update, no_update, no_update, no_update
                
            conv = filters.get("convention", "ipca")
            ccy = filters.get("currency", "BRL")

            kpis = _build_kpis(repo, filters=filters)
            
            ts = repo.time_series(filters=filters)
            
            value_label = f"Valor ({ccy}, {convention_label(conv)})"
            value_fig = line_time_series(ts, value_label=value_label)
            volume_fig = line_with_secondary(
                ts, value_label=value_label, quantity_label="Volume agregado"
            )

            ranking_src = repo.product_mix(filters=filters, top_n=15)
            # rename for the bar chart which expects state_name or similar label in bar_top_states
            ranking_src = ranking_src.rename(columns={"product_description": "state_name"})
            ranking_fig = bar_top_states(ranking_src, value_label=value_label)

            table = _ranking_table(repo, filters=filters)
            return kpis, value_fig, volume_fig, ranking_fig, table, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/valor-e-volume",
                where="callback de atualização de Valor e Volume",
            )
            return no_update, no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
