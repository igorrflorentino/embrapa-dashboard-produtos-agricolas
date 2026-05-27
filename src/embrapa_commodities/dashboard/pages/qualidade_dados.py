"""/ibge-pevs/qualidade-dados — Qualidade dos Dados.

Transparência sobre integridade do banco: KPIs por flag, evolução
temporal da composição, heatmap UF × ano, top produtos com pior
cobertura, e tabela bruta de drill-down. Absorve as antigas páginas
``/tabela`` e ``/glossario`` via tabela embutida e modal de ajuda
(modal será incrementado em uma sessão futura — Task #6).
"""

from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts_views import (
    heatmap_uf_year_quality,
    stacked_area_quality,
)
from embrapa_commodities.dashboard.components.global_filter_bar import (
    global_filter_bar,
    selected_commodity_codes,
    selected_data_quality,
    selected_period_years,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import fmt_number

PREFIX = "qualidade"

# Local filter: quality-flag multi-select. Defaults to ALL flags (the
# diagnostic view: show everything). Other views default to OK-only.
_ALL_FLAGS = ["OK", "MISSING_VALUE", "MISSING_QUANTITY", "INCOMPLETE"]


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
                    html.H1("Qualidade dos Dados", className="page-title"),
                    html.P(
                        "Panorama de integridade do Gold: cobertura por flag, evolução "
                        "temporal, distribuição UF × ano e drill-down ao nível de linha. "
                        "É a primeira parada quando um número em outra view parece estranho.",
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
            global_filter_bar(repo),
            html.Div(id={"section": PREFIX, "control": "kpi-row"}, className="kpi-row"),
            section_header(
                overline="Cobertura temporal",
                title="Linhas por flag de qualidade ao longo dos anos",
            ),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "stacked"},
                    config={"displayModeBar": False},
                ),
            ),
            section_header(
                overline="Cobertura geográfica",
                title="% OK por UF × ano (verde = alto · vermelho = baixo)",
            ),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "heatmap"},
                    config={"displayModeBar": False},
                ),
            ),
            section_header(
                overline="Drill-down",
                title="Tabela bruta filtrada por commodity / período / flag",
            ),
            html.Div(
                className="card",
                children=html.Div(
                    id={"section": PREFIX, "control": "table-container"},
                ),
            ),
            about_data_panel(
                sources=[
                    "**`gold_commodity_matrix`** — row-level data_quality_flag "
                    "(definido pelo macro `dbt/macros/data_quality_flag.sql`).",
                ],
                coverage_notes=[
                    "Flags possíveis: `OK` · `MISSING_VALUE` (qty presente, valor ausente) · "
                    "`MISSING_QUANTITY` (valor presente, qty ausente) · "
                    "`INCOMPLETE` (nem valor nem qty).",
                ],
                caveats=[
                    "**`MISSING_*` não é erro de pipeline.** É ausência legítima de coleta "
                    "(município x produto x ano sem declaração). O painel mede cobertura, "
                    "não correção da transformação.",
                ],
            ),
        ],
    )


# ── Callbacks ─────────────────────────────────────────────────────────────


def _build_kpis(repo: GoldRepository) -> list:
    q = repo.quality_summary()
    if not q.get("rows_total"):
        return [html.Div("Sem dados.", className="empty-state")]
    total = q["rows_total"]
    return [
        kpi_card(
            label="% de registros OK",
            value=f"{q['pct_ok']:.1f}%".replace(".", ","),
            sub=f"{fmt_number(q['rows_ok'], decimals=0)} de {fmt_number(total, decimals=0)} linhas",
        ),
        kpi_card(
            label="MISSING_VALUE",
            value=fmt_number(q["rows_missing_value"], decimals=0),
            sub=f"{100 * q['rows_missing_value'] / total:.1f}% do total".replace(".", ","),
        ),
        kpi_card(
            label="MISSING_QUANTITY",
            value=fmt_number(q["rows_missing_quantity"], decimals=0),
            sub=f"{100 * q['rows_missing_quantity'] / total:.1f}% do total".replace(".", ","),
        ),
        kpi_card(
            label="INCOMPLETE",
            value=fmt_number(q["rows_incomplete"], decimals=0),
            sub=f"{100 * q['rows_incomplete'] / total:.1f}% do total".replace(".", ","),
        ),
    ]


def _drill_table(repo: GoldRepository, *, commodities, years, flags) -> dash_table.DataTable:
    df = repo.filtered(
        years=years,
        commodity_codes=commodities,
        flags=flags,
    )
    if df.empty:
        return html.Div("Sem linhas para os filtros selecionados.", className="empty-state")
    # Keep the most relevant columns; full export remains via the header button.
    cols = [
        "reference_year",
        "state_acronym",
        "city_name",
        "product_description",
        "data_quality_flag",
        "val_yearfx_brl",
        "quantity_tons",
        "quantity_m3",
    ]
    cols = [c for c in cols if c in df.columns]
    return dash_table.DataTable(
        data=df[cols].head(1000).to_dict("records"),
        columns=[{"name": c, "id": c} for c in cols],
        page_size=20,
        sort_action="native",
        style_as_list_view=True,
        style_cell={"fontFamily": "Univers, Arial, sans-serif", "fontSize": "13px"},
        style_data_conditional=[
            {
                "if": {"filter_query": '{data_quality_flag} != "OK"'},
                "backgroundColor": "rgba(178,58,43,0.06)",
            }
        ],
    )


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "stacked"}, "figure"),
        Output({"section": PREFIX, "control": "heatmap"}, "figure"),
        Output({"section": PREFIX, "control": "table-container"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input("global-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(global_filters):
        try:
            commodities = selected_commodity_codes(global_filters)
            years = selected_period_years(global_filters)
            # data_quality is a list of tags. Defaults to _ALL_FLAGS if empty
            data_quality = selected_data_quality(global_filters) or _ALL_FLAGS

            kpis = _build_kpis(repo)
            stacked = stacked_area_quality(repo.quality_breakdown_by_year(years=years))
            heatmap = heatmap_uf_year_quality(repo.quality_by_uf_year(years=years))
            table = _drill_table(
                repo, commodities=commodities, years=years, flags=data_quality
            )
            return kpis, stacked, heatmap, table, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/qualidade-dados",
                where="callback de atualização de Qualidade dos Dados",
            )
            return no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
