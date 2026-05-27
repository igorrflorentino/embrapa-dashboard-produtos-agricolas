"""/ibge-pevs/valor-e-volume — Valor e Volume.

Eixo tempo × produto × métricas monetárias e de volume. **Sem geografia**
— sem mapas, sem rankings de UF. A view responde "como evoluíram valor e
quantidade das commodities selecionadas, em qual convenção monetária".

Substitui a antiga ``/produto`` (que misturava geografia via top-states).
"""

from __future__ import annotations

from dash import Input, Output, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts import (
    bar_top_states,
    line_time_series,
    line_with_secondary,
)
from embrapa_commodities.dashboard.components.global_filter_bar import (
    global_filter_bar,
    selected_commodity_codes,
    selected_convention,
    selected_currency,
    selected_period,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_number,
    period_to_years,
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
            global_filter_bar(repo),
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
            section_header(
                overline="Ranking",
                title="Commodities por valor no último ano",
            ),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "ranking"},
                    config={"displayModeBar": False},
                ),
            ),
            about_data_panel(
                sources=[
                    "**`gold_commodity_year_product`** — agregação nacional por (ano, commodity), "
                    "pré-calculada no Gold."
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


# ── Callbacks ─────────────────────────────────────────────────────────────


def _commodities_sub(commodities: list[str] | None) -> str:
    if not commodities:
        return "sem filtro"
    head = ", ".join(commodities[:3])
    suffix = "…" if len(commodities) > 3 else ""
    return f"filtro: {head}{suffix}"


def _build_kpis(
    repo: GoldRepository,
    *,
    commodities: list[str] | None,
    years: tuple[int, int] | None,
    conv: str,
    ccy: str,
) -> list:
    series = repo.time_series(
        convention=conv, currency=ccy, years=years, commodity_codes=commodities
    )
    if series.empty:
        return [html.Div("Sem dados.", className="empty-state")]
    total_value = float(series["value"].sum() or 0.0)
    total_qty = float(series["quantity"].sum() or 0.0)
    avg_unit = (total_value / total_qty) if total_qty else None
    n_years = len(series)
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
            sub=_commodities_sub(commodities),
        ),
    ]


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "value-line"}, "figure"),
        Output({"section": PREFIX, "control": "volume-line"}, "figure"),
        Output({"section": PREFIX, "control": "ranking"}, "figure"),
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
                convention=conv, currency=ccy, years=years, commodity_codes=commodities
            )
            value_label = f"Valor ({ccy}, {convention_label(conv)})"
            value_fig = line_time_series(ts, value_label=value_label)
            volume_fig = line_with_secondary(
                ts, value_label=value_label, quantity_label="Volume agregado"
            )

            hi_year = int(years[1] if years else repo.year_range()[1])
            # Ranking: query year_product directly to get all commodities (not
            # limited by the global filter — the user wants to see WHERE their
            # selection sits in the overall market).
            ranking_src = repo.product_mix(year=hi_year, convention=conv, currency=ccy, top_n=15)
            # product_mix returns columns: product_code, product_description, value, share.
            # Adapt to bar_top_states' expected shape (state_name, value) — reuse the bar
            # builder so the visual language stays the same.
            ranking_src = ranking_src.rename(columns={"product_description": "state_name"})
            ranking_fig = bar_top_states(ranking_src, value_label=value_label)

            return kpis, value_fig, volume_fig, ranking_fig, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/valor-e-volume",
                where="callback de atualização de Valor e Volume",
            )
            return no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
