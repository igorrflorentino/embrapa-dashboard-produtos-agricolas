"""/ibge-pevs/geografia — Geografia.

Perspectiva espacial pura: choropleth nacional, treemap região → UF,
heatmap região × ano, e tabela top-50 municípios. 
Filtros são gerenciados globalmente.
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

_CODE_TO_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip


@lru_cache(maxsize=1)
def _load_brazil_geojson() -> dict | None:
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
                        "UFs, regiões e municípios. Use os filtros globais para refinar "
                        "commodity, período, moeda e estados exibidos.",
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
                overline="Drill-down municipal", title="Top 50 municípios no último ano"
            ),
            html.Div(
                className="card",
                children=html.Div(id={"section": PREFIX, "control": "cities-table"}),
            ),
            about_data_panel(
                sources=[
                    "**`gold_commodity_matrix`** — tabela única para agregação UF × ano, "
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


# ── Callbacks ─────────────────────────────────────────────────────────────────


def _build_kpis(
    repo: GoldRepository,
    *,
    filters: dict,
) -> list:
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    year = filters.get("end_year", 2024)
    state_filter = filters.get("states", [])

    top = repo.top_states(filters=filters, n=27)
    if not top.empty and state_filter:
        top = top[top["state_acronym"].isin(state_filter)]
    if top.empty:
        return [html.Div("Sem dados.", className="empty-state")]
    
    total = float(top["value"].sum() or 0.0)
    top5 = float(top.head(5)["value"].sum() or 0.0)
    leader = top.iloc[0]
    cov = repo.coverage_summary(filters=filters)
    return [
        kpi_card(
            label="UFs com produção",
            value=str(int((top["value"] > 0).sum())),
            sub=f"de {cov.get('states', 0)} no Gold",
        ),
        kpi_card(
            label="Municípios produtores",
            value=fmt_number(cov.get("cities", 0), decimals=0),
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
    filters: dict,
) -> html.Div:
    df = repo.top_cities(filters=filters, n=50)
    
    conv = filters.get("convention", "ipca")
    ccy = filters.get("currency", "BRL")
    
    if df.empty:
        return html.Div("Sem municípios para os filtros selecionados.", className="empty-state")
    cols = [c for c in ["city_name", "state_acronym", "value", "quantity"] if c in df.columns]
    col_labels = {
        "city_name": "Município",
        "state_acronym": "UF",
        "value": f"Valor ({ccy}, {convention_label(conv)})",
        "quantity": "Quantidade (t / m³)",
    }
    return dash_table.DataTable(
        data=df[cols].to_dict("records"),
        columns=[
            {
                "name": col_labels.get(c, c),
                "id": c,
                "type": "numeric" if c in ("value", "quantity") else "text",
            }
            for c in cols
        ],
        page_size=25,
        sort_action="native",
        style_as_list_view=True,
        style_cell={"fontFamily": "Univers, Arial, sans-serif", "fontSize": "13px"},
        style_data_conditional=[
            {"if": {"column_id": "value"}, "fontFamily": "var(--font-mono)"},
            {"if": {"column_id": "quantity"}, "fontFamily": "var(--font-mono)"},
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
        Output({"section": PREFIX, "control": "choropleth"}, "figure"),
        Output({"section": PREFIX, "control": "treemap"}, "figure"),
        Output({"section": PREFIX, "control": "heatmap-region"}, "figure"),
        Output({"section": PREFIX, "control": "cities-table"}, "children"),
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

            top = repo.top_states(filters=filters, n=27)
            value_label = f"Valor ({ccy}, {convention_label(conv)})"
            choro = choropleth_brazil(top, _load_brazil_geojson(), value_label=value_label)
            tree = treemap_region_state(top, value_label=value_label)

            regional = repo.regional_aggregate(filters=filters)
            heat = heatmap_region_year(regional, value_label=value_label)

            cities = _cities_table(repo, filters=filters)
            return kpis, choro, tree, heat, cities, no_update
        except Exception as exc:
            err = build_error_payload(
                exc,
                page="/ibge-pevs/geografia",
                where="callback de atualização de Geografia",
            )
            return no_update, no_update, no_update, no_update, no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
