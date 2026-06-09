"""Valor e volume — value series + quantity series segregated by unit family."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    snap = seam.snapshot(banco_id, conv, summary)
    ov = snap["overview_ts"]
    if ov is None or ov.empty:
        return [
            card(
                html.P(
                    "Sem dados para a seleção atual.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    ov = ov.sort_values("reference_year")
    years = ov["reference_year"].tolist()
    vals = ov["total_value"].tolist()
    sym = fmt.symbol_for_column(snap["value_column"])

    kpis = [
        kpi_card(
            f"Valor · {snap['value_label']}",
            fmt.fmt_money(vals[-1], sym),
            sub=f"{years[-1]}",
            spark=basic.sparkline_svg(vals[-12:], color=basic.theme.YALE_BLUE),
        )
    ]
    qty_cards = []
    if "q_mass" in ov and float(ov["q_mass"].fillna(0).sum()) > 0:
        m = ov["q_mass"].fillna(0).tolist()
        kpis.append(
            kpi_card(
                "Quantidade · massa (t)",
                fmt.fmt_num(m[-1], "t"),
                sub=f"{years[-1]}",
                spark=basic.sparkline_svg(m[-12:], color=basic.theme.EMBRAPA_GREEN),
            )
        )
        qty_cards.append(
            card(
                [
                    section_header("Quantidade · família massa", "Total anual (t)"),
                    basic.line_area(years, m, label="t", color=basic.theme.EMBRAPA_GREEN),
                ]
            )
        )
    if "q_vol" in ov and float(ov["q_vol"].fillna(0).sum()) > 0:
        vv = ov["q_vol"].fillna(0).tolist()
        kpis.append(
            kpi_card(
                "Quantidade · volume (m³)",
                fmt.fmt_num(vv[-1], "m³"),
                sub=f"{years[-1]}",
                spark=basic.sparkline_svg(vv[-12:], color="#3A74B0"),
            )
        )
        qty_cards.append(
            card(
                [
                    section_header("Quantidade · família volume", "Total anual (m³)"),
                    basic.line_area(years, vv, label="m³", color="#3A74B0"),
                ]
            )
        )

    blocks = [
        html.Div(kpis, className="kpi-row"),
        card(
            [
                section_header(
                    f"Valor · {years[0]}–{years[-1]} · {snap['value_label']}",
                    "Série histórica de valor",
                ),
                basic.line_area(years, vals, label=sym),
            ]
        ),
    ]
    if qty_cards:
        blocks.append(html.Div(qty_cards, className="grid-2" if len(qty_cards) == 2 else "grid-1"))
    else:
        blocks.append(
            card(
                html.P(
                    "Quantidades não disponíveis para este banco.",
                    className="caption",
                    style={"padding": "16px 4px"},
                ),
                subtle=True,
            )
        )
    return blocks
