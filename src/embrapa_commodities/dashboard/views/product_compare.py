"""Comparativo entre produtos — base-100 trajectories + CAGR (M1: top 4 by value)."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header
from ..theme import VIZ_SCALE
from ._helpers import base_100, cagr


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    snap = seam.snapshot(banco_id, conv, summary)
    pts, products = snap["product_ts"], snap["products"]
    if pts is None or pts.empty:
        return [
            card(
                html.P(
                    "Sem séries de produto para comparar.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    last_year = int(pts["reference_year"].max())
    latest = pts[pts["reference_year"] == last_year].groupby("code")["total_value"].sum()
    codes = [str(c) for c in latest.sort_values(ascending=False).head(4).index]
    name_by = (
        dict(zip(products["code"], products["name"], strict=False)) if products is not None else {}
    )

    series, table_rows = [], []
    for i, code in enumerate(codes):
        s = pts[pts["code"] == code].sort_values("reference_year")
        years = s["reference_year"].tolist()
        vals = s["total_value"].tolist()
        color = VIZ_SCALE[i % len(VIZ_SCALE)]
        name = name_by.get(code, code)
        series.append({"name": name, "color": color, "xs": years, "ys": base_100(vals)})
        growth = cagr(vals[0], vals[-1], len(years) - 1) if len(vals) > 1 else None
        table_rows.append(
            html.Tr(
                [
                    html.Td([html.Span(className="ldot", style={"background": color}), " ", name]),
                    html.Td(
                        fmt.fmt_money(vals[-1], fmt.symbol_for_column(snap["value_column"])),
                        className="tnum",
                    ),
                    html.Td(
                        fmt.fmt_signed(growth) if growth is not None else "—", className="tnum"
                    ),
                ]
            )
        )

    kpis = html.Div(
        [
            kpi_card("Produtos comparados", str(len(codes)), sub="maiores por valor recente"),
            kpi_card(
                "Base de normalização", "100", sub=f"primeiro ano da série · base {last_year}"
            ),
            kpi_card(
                "Líder atual",
                name_by.get(codes[0], codes[0]) if codes else "—",
                sub=f"maior valor em {last_year}",
            ),
        ],
        className="kpi-row",
    )

    table = html.Table(
        [
            html.Thead(html.Tr([html.Th("Produto"), html.Th("Valor atual"), html.Th("CAGR")])),
            html.Tbody(table_rows),
        ],
        className="cmp-table",
    )

    return [
        kpis,
        card(
            [
                section_header(
                    "Trajetórias normalizadas (base 100)",
                    "Crescimento relativo desde o início da série",
                ),
                basic.multi_line(series, label="Índice (base 100)", height=300),
            ]
        ),
        card(
            [
                section_header(
                    "Métricas comparativas", "Valor recente e crescimento composto (CAGR)"
                ),
                table,
            ]
        ),
    ]
