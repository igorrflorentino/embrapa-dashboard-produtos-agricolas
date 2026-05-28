"""/ibge-pevs/qualidade-dados — Qualidade dos Dados.

Transparência sobre integridade do banco: KPIs por flag, evolução
temporal da composição, heatmap UF × ano, e tabela de drill-down.
Filtros gerenciados globalmente.
"""

from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts_views import (
    heatmap_uf_year_quality,
    stacked_area_quality,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import fmt_number

PREFIX = "qualidade"

_FLAG_CHIP = {
    "OK": "ok",
    "MISSING_VALUE": "warn",
    "MISSING_QUANTITY": "warn",
    "INCOMPLETE": "err",
}
_COL_LABELS = {
    "reference_year": "Ano",
    "state_acronym": "UF",
    "city_name": "Município",
    "product_description": "Commodity",
    "data_quality_flag": "Flag de qualidade",
    "val_yearfx_brl": "Valor nominal (R$)",
    "quantity_tons": "Qtd. (t)",
    "quantity_m3": "Qtd. (m³)",
}


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
                title="Registros filtrados por commodity, período e flag",
            ),
            html.Div(
                className="card",
                children=html.Div(id={"section": PREFIX, "control": "table-container"}),
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


# ── Callbacks ─────────────────────────────────────────────────────────────────


def _build_kpis(repo: GoldRepository, filters: dict) -> list:
    q = repo.quality_summary(filters=filters)
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


def _drill_table(repo: GoldRepository, *, filters: dict) -> html.Div:
    df = repo.filtered(filters=filters)
    if df.empty:
        return html.Div("Sem linhas para os filtros selecionados.", className="empty-state")
    raw_cols = [
        "reference_year",
        "state_acronym",
        "city_name",
        "product_description",
        "data_quality_flag",
        "val_yearfx_brl",
        "quantity_tons",
        "quantity_m3",
    ]
    cols = [c for c in raw_cols if c in df.columns]
    columns = [{"name": _COL_LABELS.get(c, c), "id": c} for c in cols]
    return dash_table.DataTable(
        data=df[cols].head(1000).to_dict("records"),
        columns=columns,
        page_size=20,
        sort_action="native",
        filter_action="native",
        style_as_list_view=True,
        style_cell={"fontFamily": "Univers, Arial, sans-serif", "fontSize": "13px"},
        style_data_conditional=[
            {
                "if": {"filter_query": '{data_quality_flag} != "OK"'},
                "backgroundColor": "rgba(178,58,43,0.06)",
            },
            {
                "if": {
                    "column_id": "data_quality_flag",
                    "filter_query": '{data_quality_flag} = "OK"',
                },
                "color": "var(--embrapa-green-darker)",
                "fontWeight": "500",
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
        Output({"section": PREFIX, "control": "stacked"}, "figure"),
        Output({"section": PREFIX, "control": "heatmap"}, "figure"),
        Output({"section": PREFIX, "control": "table-container"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input("global-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(filters):
        try:
            if not filters:
                return no_update, no_update, no_update, no_update, no_update
                
            kpis = _build_kpis(repo, filters=filters)
            stacked = stacked_area_quality(repo.quality_breakdown_by_year(filters=filters))
            heatmap = heatmap_uf_year_quality(repo.quality_by_uf_year(filters=filters))
            table = _drill_table(repo, filters=filters)
            return kpis, stacked, heatmap, table, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/qualidade-dados",
                where="callback de atualização de Qualidade dos Dados",
            )
            return no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
