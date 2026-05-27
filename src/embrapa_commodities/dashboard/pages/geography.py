"""/ibge-pevs/geografia — Geografia.

Perspectiva espacial pura: choropleth nacional, treemap região → UF,
heatmap região × ano, e tabela top-50 municípios. Commodity é apenas
um filtro (vem do global filter bar); não há análise por produto aqui
— para isso, abra a view Valor e Volume.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import requests
from dash import Input, Output, dash_table, dcc, html, no_update

from embrapa_commodities.dashboard.components.about_data_panel import about_data_panel
from embrapa_commodities.dashboard.components.charts import choropleth_brazil
from embrapa_commodities.dashboard.components.charts_views import (
    heatmap_region_year,
    treemap_region_state,
)
from embrapa_commodities.dashboard.components.global_filter_bar import (
    global_filter_bar,
    selected_commodity_codes,
    selected_convention,
    selected_currency,
    selected_period_years,
)
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldRepository
from embrapa_commodities.dashboard.formatting import (
    convention_label,
    fmt_currency,
    fmt_number,
)

PREFIX = "geography"
_log = logging.getLogger(__name__)
IBGE_GEOJSON_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados"
    "?formato=application/vnd.geo+json&intrarregiao=UF"
)


@lru_cache(maxsize=1)
def _load_brazil_geojson() -> dict | None:
    """Fetch the Brazil-by-UF GeoJSON once. Falls back to None (and the
    choropleth's bar-fallback kicks in) when IBGE's endpoint hiccups."""
    try:
        resp = requests.get(IBGE_GEOJSON_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for feat in data.get("features", []):
            cod = str(feat["properties"].get("codarea", "")).strip()
            sigla = _CODE_TO_SIGLA.get(cod)
            if sigla:
                feat["properties"]["sigla"] = sigla
        return data
    except Exception as exc:
        _log.warning("Failed to fetch Brazil GeoJSON: %s", exc)
        return None


# IBGE GeoJSON keys UFs by their numeric `codarea`; the dashboard joins on
# the 2-letter sigla, so we attach it server-side at fetch time.
_CODE_TO_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip


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
                    html.H1("Geografia", className="page-title"),
                    html.P(
                        "Onde a produção extrativa vegetal está concentrada — em quais "
                        "UFs, regiões e municípios. Commodity, período e moeda vêm do "
                        "filtro global; abaixo, o detalhamento espacial.",
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
            section_header(overline="Distribuição estadual", title="Brasil por UF"),
            html.Div(
                className="grid-2",
                children=[
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "choropleth"},
                            config={"displayModeBar": False},
                        ),
                    ),
                    html.Div(
                        className="card",
                        children=dcc.Graph(
                            id={"section": PREFIX, "control": "treemap"},
                            config={"displayModeBar": False},
                        ),
                    ),
                ],
            ),
            section_header(
                overline="Evolução regional",
                title="Norte / Nordeste / Centro-Oeste / Sudeste / Sul × ano",
            ),
            html.Div(
                className="card",
                children=dcc.Graph(
                    id={"section": PREFIX, "control": "heatmap-region"},
                    config={"displayModeBar": False},
                ),
            ),
            section_header(
                overline="Drill-down municipal",
                title="Top 50 municípios no último ano",
            ),
            html.Div(
                className="card",
                children=html.Div(id={"section": PREFIX, "control": "cities-table"}),
            ),
            about_data_panel(
                sources=[
                    "**`gold_commodity_state_total_year`** — agregado UF × ano sem produto, "
                    "fonte primária do choropleth e do treemap.",
                    "**IBGE GeoJSON** — malha estadual (intrarregiao=UF) buscada em "
                    "runtime do `servicodados.ibge.gov.br`; fallback para barras "
                    "horizontais se a API falhar.",
                ],
                coverage_notes=[
                    "Códigos municipais mudam historicamente (emancipações / fusões). "
                    "Linhas pré-2000 podem não casar com a malha atual — pequenas lacunas "
                    "no drill-down são esperadas, não erro de pipeline.",
                ],
                caveats=[],
            ),
        ],
    )


# ── Callbacks ─────────────────────────────────────────────────────────────


def _build_kpis(
    repo: GoldRepository,
    *,
    commodities: list[str] | None,
    conv: str,
    ccy: str,
    year: int,
) -> list:
    top = repo.top_states(
        year=year, convention=conv, currency=ccy, commodity_codes=commodities, n=27
    )
    if top.empty:
        return [html.Div("Sem dados.", className="empty-state")]
    total = float(top["value"].sum() or 0.0)
    top5 = float(top.head(5)["value"].sum() or 0.0)
    leader = top.iloc[0]
    cov = repo.coverage_summary(year=year)
    return [
        kpi_card(
            label="UFs com produção",
            value=str(int((top["value"] > 0).sum())),
            sub=f"de {cov['states']} no Gold",
        ),
        kpi_card(
            label="Municípios produtores",
            value=fmt_number(cov["cities"], decimals=0),
            sub=f"distintos · ano {year}",
        ),
        kpi_card(
            label="Concentração (top 5 UFs)",
            value=f"{100 * top5 / total:.1f}%".replace(".", ",") if total else "—",
            sub="share do valor total",
        ),
        kpi_card(
            label="UF líder",
            value=f"{leader.state_name}",
            sub=f"{fmt_currency(float(leader.value), ccy)} · {convention_label(conv)}",
        ),
    ]


def _cities_table(
    repo: GoldRepository,
    *,
    commodities: list[str] | None,
    conv: str,
    ccy: str,
    year: int,
) -> html.Div:
    df = repo.top_cities(
        year=year,
        convention=conv,
        currency=ccy,
        commodity_codes=commodities,
        n=50,
    )
    if df.empty:
        return html.Div("Sem municípios para os filtros selecionados.", className="empty-state")
    cols = ["city_name", "state_acronym", "value", "quantity"]
    return dash_table.DataTable(
        data=df[cols].to_dict("records"),
        columns=[
            {"name": "Município", "id": "city_name"},
            {"name": "UF", "id": "state_acronym"},
            {"name": f"Valor ({ccy})", "id": "value", "type": "numeric"},
            {"name": "Quantidade", "id": "quantity", "type": "numeric"},
        ],
        page_size=25,
        sort_action="native",
        style_as_list_view=True,
        style_cell={"fontFamily": "Univers, Arial, sans-serif", "fontSize": "13px"},
    )


def register_callbacks(app, repo: GoldRepository) -> None:
    from embrapa_commodities.dashboard.app import build_error_payload

    @app.callback(
        Output({"section": PREFIX, "control": "kpi-row"}, "children"),
        Output({"section": PREFIX, "control": "choropleth"}, "figure"),
        Output({"section": PREFIX, "control": "treemap"}, "figure"),
        Output({"section": PREFIX, "control": "heatmap-region"}, "figure"),
        Output({"section": PREFIX, "control": "cities-table"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input("global-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(global_filters):
        try:
            commodities = selected_commodity_codes(global_filters)
            conv = selected_convention(global_filters)
            ccy = selected_currency(global_filters)
            years = selected_period_years(global_filters)
            year = int(years[1] if years else repo.year_range()[1])

            kpis = _build_kpis(repo, commodities=commodities, conv=conv, ccy=ccy, year=year)

            top = repo.top_states(
                year=year, convention=conv, currency=ccy, commodity_codes=commodities, n=27
            )
            value_label = f"Valor ({ccy}, {convention_label(conv)})"
            choro = choropleth_brazil(top, _load_brazil_geojson(), value_label=value_label)
            tree = treemap_region_state(top, value_label=value_label)

            regional = repo.regional_aggregate(
                convention=conv, currency=ccy, commodity_codes=commodities, years=years
            )
            heat = heatmap_region_year(regional, value_label=value_label)

            cities = _cities_table(repo, commodities=commodities, conv=conv, ccy=ccy, year=year)
            return kpis, choro, tree, heat, cities, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/geografia",
                where="callback de atualização de Geografia",
            )
            return no_update, no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
