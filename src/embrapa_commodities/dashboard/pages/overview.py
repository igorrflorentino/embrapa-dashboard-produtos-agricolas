"""/ibge-pevs/visao-geral — Visão Geral.

Strategic snapshot of Brazilian extractive vegetable production. Reads the
analytical "lens" (commodity / period / currency / convention) from the
session-scoped global filter store. The view itself has no local controls
— quality is fixed to OK rows because Visão Geral is meant to be the
trusted scoreboard; deeper integrity work lives in Qualidade dos Dados.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    donut_product_mix,
    line_time_series,
)
from embrapa_commodities.dashboard.components.global_filter_bar import (
    global_filter_bar,
    selected_commodity_codes,
    selected_convention,
    selected_currency,
    selected_period,
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
    period_to_years,
)

PREFIX = "overview"


# ── Layout ────────────────────────────────────────────────────────────────


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
            global_filter_bar(repo),
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


# ── Callbacks ─────────────────────────────────────────────────────────────


def _build_kpis(
    repo: GoldRepository,
    *,
    commodities: list[str] | None,
    years: tuple[int, int] | None,
    conv: str,
    ccy: str,
) -> list:
    series = repo.time_series(
        convention=conv,
        currency=ccy,
        years=years,
        commodity_codes=commodities,
    )
    if series.empty:
        return [_empty_kpi("Sem dados para os filtros selecionados.")]
    total_value = float(series["value"].sum() or 0.0)
    total_qty = float(series["quantity"].sum() or 0.0)
    last_year = int(series["reference_year"].max())
    last_val = float(series.loc[series["reference_year"] == last_year, "value"].iloc[0])
    prev = series[series["reference_year"] == last_year - 1]
    yoy = None
    if not prev.empty and prev["value"].iloc[0]:
        yoy = (last_val - float(prev["value"].iloc[0])) / float(prev["value"].iloc[0]) * 100.0
    cov = repo.coverage_summary(year=last_year)
    return [
        kpi_card(
            label=f"Valor agregado · {convention_label(conv)} · {ccy}",
            value=fmt_currency(total_value, ccy),
            sub=f"soma {years[0] if years else '—'}–{last_year}",
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


def _empty_kpi(message: str) -> html.Div:
    return html.Div(className="empty-state", children=html.P(message))


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "time-series"}, "figure"),
        Output({"section": PREFIX, "control": "donut"}, "figure"),
        Output({"section": PREFIX, "control": "top-states"}, "figure"),
        Output("global-error", "data", allow_duplicate=True),
        Input("global-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(global_filters):
        try:
            commodities = selected_commodity_codes(global_filters)
            conv = selected_convention(global_filters)
            ccy = selected_currency(global_filters)
            period = selected_period(global_filters)
            years = period_to_years(repo.year_range(), period)

            kpis = _build_kpis(repo, commodities=commodities, years=years, conv=conv, ccy=ccy)
            ts = repo.time_series(
                convention=conv,
                currency=ccy,
                years=years,
                commodity_codes=commodities,
            )
            ts_fig = line_time_series(ts, value_label=f"Valor ({ccy}, {convention_label(conv)})")

            hi_year = int(repo.year_range()[1] if not years else years[1])
            mix = repo.product_mix(year=hi_year, convention=conv, currency=ccy, top_n=6)
            donut_fig = donut_product_mix(mix)

            top = repo.top_states(
                year=hi_year,
                convention=conv,
                currency=ccy,
                commodity_codes=commodities,
                n=5,
            )
            top_fig = bar_top_states(top, value_label=f"Valor ({ccy}, {convention_label(conv)})")

            return kpis, ts_fig, donut_fig, top_fig, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/visao-geral",
                where="callback de atualização da Visão Geral",
            )
            return no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
