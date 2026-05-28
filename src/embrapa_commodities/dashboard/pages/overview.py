"""/ibge-pevs/visao-geral — Visão Geral.

Strategic snapshot of Brazilian extractive vegetable production.
Filters are now globally managed.
"""

from __future__ import annotations

from dash import Input, Output, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    donut_product_mix,
    line_time_series,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.monetary_legend import monetary_legend
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_datetime,
    fmt_delta,
    fmt_number,
)

PREFIX = "overview"


# ── Layout ────────────────────────────────────────────────────────────────────


def _hero(repo: GoldRepository) -> html.Div:
    last_refresh = repo.last_refresh()
    last_refresh_str = fmt_datetime(last_refresh) if last_refresh else "—"
    lo, hi = repo.year_range()
    return html.Div(
        className="page-hero",
        children=[
            html.Div(
                children=[
                    html.Div(
                        "Dashboard de Inteligência de Mercado · Commodities",
                        className="overline",
                    ),
                    html.H1(
                        "Visão Geral · Produção extrativa vegetal",
                        className="page-title",
                    ),
                    html.P(
                        children=[
                            "Resumo estratégico da produção brasileira extrativa vegetal — ",
                            "pipeline Bronze → Silver → Gold sobre IBGE PEVS, com correção ",
                            "monetária por IPCA / IGP-M / IGP-DI e conversão cambial. Cobertura: ",
                            html.Strong(f"{lo}–{hi}"),
                            ".",
                        ],
                        className="page-sub",
                    ),
                ]
            ),
            html.Div(
                className="hero-meta",
                children=[
                    html.Div(
                        className="meta-row",
                        children=[
                            html.Span("Última carga do Gold", className="meta-label"),
                            html.Span(last_refresh_str, className="meta-val tnum"),
                        ],
                    ),
                ],
            ),
        ],
    )


def layout(repo: GoldRepository) -> html.Div:
    return html.Div(
        className="screen",
        children=[
            _hero(repo),
            html.Div(id={"section": PREFIX, "control": "kpi-row"}, className="kpi-row"),
            section_header(overline="Tendência", title="Evolução histórica"),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "time-series"},
                            config={"displayModeBar": False},
                        ),
                    ),
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "donut"},
                            config={"displayModeBar": False},
                        ),
                    ),
                ],
            ),
            section_header(overline="Concentração geográfica", title="Top 5 estados"),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "top-states"},
                    config={"displayModeBar": False},
                ),
            ),
            section_header(overline="Resumo por commodity", title="Valor e volume no último ano"),
            html.Div(
                className="card",
                children=html.Div(id={"section": PREFIX, "control": "summary-table"}),
            ),
            monetary_legend(),
            about_data_panel(
                sources=[
                    "**IBGE PEVS** — Pesquisa da Extração Vegetal e da Silvicultura "
                    "([sidra.ibge.gov.br/tabela/289](https://sidra.ibge.gov.br/tabela/289))",
                    "**BCB SGS** — IPCA (433), IGP-M (189), IGP-DI (190); câmbio USD/EUR/CNY",
                ],
                coverage_notes=[
                    "Valores pré-1994 ficam em **R$ corrente** (Silver absorve as reformas "
                    "monetárias via `historical_currency_factors`); colunas em USD/EUR/CNY "
                    "são NULL para anos sem câmbio publicado.",
                ],
                caveats=[
                    "A view filtra apenas linhas com `data_quality_flag = OK`. "
                    "Diagnóstico completo de qualidade fica em **Qualidade dos Dados**.",
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
        return [_empty("Sem dados para os filtros selecionados.")]
    total_value = float(series["value"].sum() or 0.0)
    total_qty = float(series["quantity"].sum() or 0.0)
    last_year = int(series["reference_year"].max())
    last_val = float(series.loc[series["reference_year"] == last_year, "value"].iloc[0])
    prev = series[series["reference_year"] == last_year - 1]
    yoy = None
    if not prev.empty and prev["value"].iloc[0]:
        yoy = (last_val - float(prev["value"].iloc[0])) / float(prev["value"].iloc[0]) * 100.0
    
    # Coverage summary expects filters
    cov = repo.coverage_summary(filters=filters)
    
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    lo = filters.get("start_year", 1986)
    
    return [
        kpi_card(
            label=f"Valor agregado · {convention_label(conv)} · {ccy}",
            value=fmt_currency(total_value, ccy),
            sub=f"soma {lo}–{last_year}",
        ),
        kpi_card(
            label="Volume agregado",
            value=fmt_number(total_qty, decimals=0),
            sub="unidade dominante (t / m³)",
        ),
        kpi_card(
            label=f"Variação YoY · {last_year}",
            value=fmt_delta(yoy) if yoy is not None else "—",
            sub=f"vs. {last_year - 1}",
        ),
        kpi_card(
            label="Cobertura no último ano",
            value=f"{cov['states']} UFs · {cov['cities']:,} mun.".replace(",", "."),
            sub=f"{cov['products']} commodity(ies)",
        ),
    ]


def _summary_table(
    repo: GoldRepository,
    *,
    filters: dict,
) -> html.Div:
    df = repo.product_mix(filters=filters, top_n=20)
    if df.empty:
        return _empty("Sem dados para os filtros selecionados.")
    cols_show = [c for c in ["product_description", "value", "share"] if c in df.columns]
    
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    
    col_labels = {
        "product_description": "Commodity",
        "value": f"Valor ({ccy}, {convention_label(conv)})",
        "share": "Share (%)",
    }
    return dash_table.DataTable(
        data=df[cols_show].to_dict("records"),
        columns=[
            {
                "name": col_labels.get(c, c),
                "id": c,
                "type": "numeric" if c != "product_description" else "text",
            }
            for c in cols_show
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
    )


def _empty(message: str) -> html.Div:
    return html.Div(className="empty-state", children=html.P(message))


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "time-series"}, "figure"),
        Output({"section": PREFIX, "control": "donut"}, "figure"),
        Output({"section": PREFIX, "control": "top-states"}, "figure"),
        Output({"section": PREFIX, "control": "summary-table"}, "children"),
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
            ts_fig = line_time_series(ts, value_label=f"Valor ({ccy}, {convention_label(conv)})")

            mix = repo.product_mix(filters=filters, top_n=6)
            donut_fig = donut_product_mix(mix)

            top = repo.top_states(filters=filters, n=5)
            top_fig = bar_top_states(top, value_label=f"Valor ({ccy}, {convention_label(conv)})")

            table = _summary_table(repo, filters=filters)
            
            return kpis, ts_fig, donut_fig, top_fig, table, no_update
        except Exception as exc:
            err = build_error_payload(
                exc, page="/ibge-pevs/visao-geral", where="callback de atualização da Visão Geral"
            )
            return no_update, no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
