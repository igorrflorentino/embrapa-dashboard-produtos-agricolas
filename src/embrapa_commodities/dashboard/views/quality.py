"""Qualidade dos dados — data_quality_flag distribution."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header

# Flag id → (pt-BR label, CSS-var color for HTML dots, hex for Plotly).
QUALITY_FLAG_META: dict[str, tuple[str, str, str]] = {
    "OK": ("OK", "var(--ok)", "#006f35"),
    "MISSING_VALUE": ("Valor ausente", "var(--warn)", "#B7791F"),
    "MISSING_QUANTITY": ("Quantidade ausente", "var(--info)", "#06617c"),
    "MISSING_WEIGHT": ("Peso ausente", "var(--viz-7)", "#0e3b65"),
    "INCOMPLETE": ("Incompleto", "var(--err)", "#B23A2B"),
    "ESTIMATED": ("Estimado", "var(--viz-4)", "#3A74B0"),
    "OUTLIER": ("Outlier", "var(--err)", "#B23A2B"),
    "BOUNDARY_HISTORIC": ("Limite histórico", "var(--viz-7)", "#0e3b65"),
}


def _meta(flag: str) -> tuple[str, str, str]:
    return QUALITY_FLAG_META.get(flag, (flag, "var(--fg-3)", "#666666"))


def qa_rows(quality_df) -> html.Div:
    """The qa-summary list (dot · label · count · share) shared with Visão geral."""
    rows = []
    for _, r in quality_df.iterrows():
        label, color, _ = _meta(r["data_quality_flag"])
        rows.append(
            html.Div(
                [
                    html.Span(className="qa-dot", style={"background": color}),
                    html.Span(label, className="qa-label"),
                    html.Span(fmt.fmt_rows(r["n_rows"]), className="qa-count tnum"),
                    html.Span(fmt.fmt_pct(r["share"]), className="qa-share tnum"),
                ],
                className="qa-row",
            )
        )
    return html.Div(rows, className="qa-summary")


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    snap = seam.snapshot(banco_id, conv, summary)
    q = snap["quality"]
    if q is None or q.empty:
        return [
            card(
                html.P(
                    "Sem dados de qualidade para o banco selecionado.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    q = q.sort_values("n_rows", ascending=False)
    total = float(q["n_rows"].sum())
    ok = q[q["data_quality_flag"] == "OK"]
    ok_share = float(ok["share"].iloc[0]) if not ok.empty else 0.0
    worst = q[q["data_quality_flag"] != "OK"].head(1)
    worst_label = _meta(worst["data_quality_flag"].iloc[0])[0] if not worst.empty else "—"

    kpis = html.Div(
        [
            kpi_card(
                "Linhas íntegras (flag = OK)",
                fmt.fmt_pct(ok_share),
                sub=f"{fmt.fmt_rows(total)} linhas no total",
            ),
            kpi_card("Total de linhas", fmt.fmt_rows(total), sub="na tabela Gold do banco"),
            kpi_card("Flags distintas", str(len(q)), sub="dimensões de qualidade"),
            kpi_card(
                "Principal ressalva",
                worst_label,
                sub=fmt.fmt_pct(float(worst["share"].iloc[0])) if not worst.empty else "—",
            ),
        ],
        className="kpi-row",
    )

    labels = [_meta(f)[0] for f in q["data_quality_flag"]]
    colors = [_meta(f)[2] for f in q["data_quality_flag"]]
    values = q["n_rows"].tolist()

    grid = html.Div(
        [
            card(
                [
                    section_header(
                        "Distribuição de flags", "Participação por bandeira de qualidade"
                    ),
                    basic.donut(labels, values, colors=colors),
                ]
            ),
            card(
                [
                    section_header("Detalhamento", "Contagem e participação por flag"),
                    qa_rows(q),
                ]
            ),
        ],
        className="grid-2",
    )

    return [kpis, grid]
