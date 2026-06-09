"""Fluxos territoriais — origin→destination Sankey + top routes (COMEX/COMTRADE)."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import flow as flowcharts
from ..components.cards import card, kpi_card, section_header
from ..registries import banco_by_id


def _empty() -> list:
    return [
        card(
            html.P(
                "Sem fluxos origem → destino para a seleção atual.",
                className="caption",
                style={"padding": "24px 4px"},
            ),
            subtle=True,
        )
    ]


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    fd = seam.flow_data(banco_id, summary)
    if not fd or fd["links"] is None or fd["links"].empty:
        return _empty()
    links = fd["links"].copy()
    links["value_usd"] = links["value_usd"].fillna(0)
    links = links[links["value_usd"] > 0]
    if links.empty:
        return _empty()
    o_lab, d_lab = fd["origin_label"], fd["dest_label"]
    total = float(links["value_usd"].sum())
    by_o = (
        links.groupby("origin_code")
        .agg(name=("origin_name", "first"), v=("value_usd", "sum"))
        .sort_values("v", ascending=False)
    )
    by_d = (
        links.groupby("dest_code")
        .agg(name=("dest_name", "first"), v=("value_usd", "sum"))
        .sort_values("v", ascending=False)
    )

    kpis = html.Div(
        [
            kpi_card(
                "Fluxo total", fmt.fmt_money(total, "US$"), sub=f"{len(links)} rotas mapeadas"
            ),
            kpi_card(
                f"Maior origem · {o_lab}",
                str(by_o.iloc[0]["name"]),
                sub=fmt.fmt_money(float(by_o.iloc[0]["v"]), "US$"),
            ),
            kpi_card(
                f"Maior destino · {d_lab}",
                str(by_d.iloc[0]["name"]),
                sub=fmt.fmt_money(float(by_d.iloc[0]["v"]), "US$"),
            ),
            kpi_card("Granularidade", banco.scope, sub=banco.domain),
        ],
        className="kpi-row",
    )

    sankey_card = card(
        [
            section_header(
                f"Diagrama de fluxo · {o_lab} → {d_lab}",
                "Para onde a produção vai",
                action=html.Span("US$ · exportação + importação", className="caption"),
            ),
            flowcharts.sankey(links, o_lab, d_lab),
        ]
    )

    top_links = links.sort_values("value_usd", ascending=False).head(8)
    mx = float(top_links["value_usd"].max()) or 1.0
    routes = [
        html.Div(
            [
                html.Span(
                    [
                        str(r.origin_name),
                        html.Span(" → ", className="flow-arrow"),
                        str(r.dest_name),
                    ],
                    className="flow-route-od",
                ),
                html.Div(
                    html.Div(style={"width": f"{r.value_usd / mx * 100:.1f}%"}),
                    className="flow-route-bar",
                ),
                html.Span(
                    fmt.fmt_money(float(r.value_usd), "US$"), className="flow-route-val tnum"
                ),
            ],
            className="flow-route",
        )
        for r in top_links.itertuples()
    ]
    routes_card = card(
        [
            section_header("Rotas principais", f"Maiores fluxos {o_lab} → {d_lab}"),
            html.Div(routes, className="flow-routes"),
        ]
    )
    return [kpis, sankey_card, routes_card]
