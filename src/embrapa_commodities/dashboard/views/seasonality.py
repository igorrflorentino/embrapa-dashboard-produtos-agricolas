"""Sazonalidade e tendências — month×year heatmap + seasonal profile (COMEX only)."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import flow as flowcharts
from ..components.cards import card, kpi_card, section_header


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    df = seam.monthly_data(banco_id, summary)
    if df is None or df.empty:
        return [
            card(
                html.P(
                    "Sem granularidade mensal para a seleção atual.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    df = df.copy()
    df["total_value_usd"] = df["total_value_usd"].fillna(0)
    years = sorted(int(y) for y in df["reference_year"].unique())
    avg = df.groupby("reference_month")["total_value_usd"].mean()
    avg12 = [float(avg.get(m, 0)) for m in range(1, 13)]
    peak = max(range(12), key=lambda i: avg12[i])
    low = min(range(12), key=lambda i: avg12[i])
    amplitude = (avg12[peak] / avg12[low]) if avg12[low] else 0.0

    kpis = html.Div(
        [
            kpi_card(
                "Mês de pico",
                fmt.MONTH_ABBR_PT[peak],
                sub=f"{fmt.fmt_money(avg12[peak], 'US$')} (média)",
            ),
            kpi_card(
                "Mês de vale",
                fmt.MONTH_ABBR_PT[low],
                sub=f"{fmt.fmt_money(avg12[low], 'US$')} (média)",
            ),
            kpi_card(
                "Amplitude sazonal", "×" + fmt.fmt_num(amplitude, decimals=2), sub="pico ÷ vale"
            ),
            kpi_card("Cobertura", f"{len(years)} anos", sub=f"{years[0]}–{years[-1]}"),
        ],
        className="kpi-row",
    )

    heat = card(
        [
            section_header(
                "Mapa de calor · mês × ano",
                "Padrão sazonal ao longo dos anos",
                action=html.Span("US$ · valor exportado/importado", className="caption"),
            ),
            flowcharts.month_year_heatmap(df),
        ]
    )
    avg_card = card(
        [
            section_header("Perfil sazonal médio", "Média de cada mês no período"),
            flowcharts.monthly_bars(avg12),
        ]
    )
    return [kpis, heat, avg_card]
