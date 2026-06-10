"""Concentração e desigualdade — Lorenz / Gini / HHI by geography and product."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header
from ..registries import banco_by_id
from ._helpers import gini, hhi, lorenz_points, top_n_share


def _hhi_label(value: float) -> str:
    if value >= 2500:
        return "alta"
    if value >= 1500:
        return "moderada"
    return "baixa"


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    snap = seam.snapshot(banco_id, conv, summary)
    pts = snap["product_ts"]
    uf = snap["uf_data"]
    cards = []
    kpis = []

    has_geo = "geo" in banco.provides and uf is not None and not uf.empty
    if has_geo:
        uf_vals = [v for v in uf["total_value"].tolist() if v and v > 0]
        g_uf, h_uf = gini(uf_vals), hhi(uf_vals)
        kpis += [
            kpi_card(
                "Gini · geográfico",
                fmt.fmt_num(g_uf, decimals=3),
                sub="0 = uniforme · 1 = concentrado",
            ),
            kpi_card(
                "HHI · UFs", fmt.fmt_num(h_uf, decimals=0), sub=f"concentração {_hhi_label(h_uf)}"
            ),
            kpi_card(
                "Participação top 5 UFs",
                fmt.fmt_pct(top_n_share(uf_vals, 5)),
                sub=f"de {len(uf_vals)} UFs",
            ),
        ]
        cards.append(
            card(
                [
                    section_header(
                        "Curva de Lorenz · UFs", "Desigualdade na distribuição territorial"
                    ),
                    basic.lorenz(lorenz_points(uf_vals), label="Participação acumulada no valor"),
                ]
            )
        )

    if pts is not None and not pts.empty:
        last_year = int(pts["reference_year"].max())
        prod_vals = (
            pts[pts["reference_year"] == last_year].groupby("code")["total_value"].sum().tolist()
        )
        prod_vals = [v for v in prod_vals if v and v > 0]
        g_p = gini(prod_vals)
        kpis.append(
            kpi_card(
                "Gini · produtos",
                fmt.fmt_num(g_p, decimals=3),
                sub=f"entre {len(prod_vals)} produtos · {last_year}",
            )
        )
        cards.append(
            card(
                [
                    section_header(
                        "Curva de Lorenz · produtos", "Concentração da cesta de commodities"
                    ),
                    basic.lorenz(lorenz_points(prod_vals), label="Participação acumulada no valor"),
                ]
            )
        )

    if not cards:
        return [
            card(
                html.P(
                    "Sem dados suficientes para a análise de concentração.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    grid = html.Div(cards, className="grid-2" if len(cards) == 2 else "grid-1")
    return [html.Div(kpis, className="kpi-row"), grid]
