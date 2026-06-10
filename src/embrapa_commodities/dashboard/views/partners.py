"""Parceiros comerciais — partner ranking with export/import split (COMEX/COMTRADE)."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..components.cards import card, kpi_card, section_header
from ..registries import banco_by_id


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    df = seam.partner_data(banco_id, summary)
    if df is None or df.empty:
        return [
            card(
                html.P(
                    "Sem parceiros comerciais para a seleção atual.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    df = df.fillna(0).sort_values("value_usd", ascending=False)
    total = float(df["value_usd"].sum()) or 1.0
    top = df.iloc[0]
    top3 = float(df.head(3)["value_usd"].sum()) / total
    flow_label = banco.dimensions.get("partner", {}).get("label", "parceiro")

    kpis = html.Div(
        [
            kpi_card(
                f"Maior {flow_label}",
                str(top["partner_name"]),
                sub=fmt.fmt_money(float(top["value_usd"]), "US$"),
            ),
            kpi_card(
                "Parceiros mapeados", str(len(df)), sub=f"fluxo total {fmt.fmt_money(total, 'US$')}"
            ),
            kpi_card("Concentração top-3", fmt.fmt_pct(top3), sub="do fluxo total"),
            kpi_card("Granularidade", banco.scope, sub=banco.domain),
        ],
        className="kpi-row",
    )

    mx = float(df["value_usd"].max()) or 1.0
    rows = []
    for i, r in enumerate(df.head(15).itertuples(), start=1):
        rows.append(
            html.Div(
                [
                    html.Span(f"#{i}", className="ptn-rank tnum"),
                    html.Span(str(r.partner_name), className="ptn-name"),
                    html.Div(
                        [
                            html.Div(
                                className="ptn-bar exp",
                                style={"width": f"{r.exp_value_usd / mx * 100:.1f}%"},
                                title=f"Exportação {fmt.fmt_money(float(r.exp_value_usd), 'US$')}",
                            ),
                            html.Div(
                                className="ptn-bar imp",
                                style={"width": f"{r.imp_value_usd / mx * 100:.1f}%"},
                                title=f"Importação {fmt.fmt_money(float(r.imp_value_usd), 'US$')}",
                            ),
                        ],
                        className="ptn-bars",
                    ),
                    html.Span(fmt.fmt_money(float(r.value_usd), "US$"), className="ptn-val tnum"),
                ],
                className="ptn-row",
            )
        )

    legend = html.Div(
        [
            html.Span(
                [html.Span(className="ptn-legend-dot exp"), "Exportação"],
                className="ptn-legend-item",
            ),
            html.Span(
                [html.Span(className="ptn-legend-dot imp"), "Importação"],
                className="ptn-legend-item",
            ),
        ],
        className="ptn-legend",
    )

    ranking = card(
        [
            section_header(
                f"Ranking · {flow_label}",
                "Maiores parceiros comerciais",
                action=html.Span(f"{len(df)} parceiros", className="caption"),
            ),
            html.Div(rows, className="ptn-list"),
            legend,
        ]
    )
    return [kpis, ranking]
