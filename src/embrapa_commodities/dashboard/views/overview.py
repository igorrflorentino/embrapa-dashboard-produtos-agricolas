"""Visão geral — a digest of value, composition, geography, and quality."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..charts import geo as geocharts
from ..components.cards import card, kpi_card, section_header
from ..registries import banco_by_id
from ._helpers import composition_latest
from .quality import qa_rows


def _empty() -> list:
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


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    snap = seam.snapshot(banco_id, conv, summary)
    ov = snap["overview_ts"]
    if ov is None or ov.empty:
        return _empty()
    ov = ov.sort_values("reference_year")
    years = ov["reference_year"].tolist()
    vals = ov["total_value"].tolist()
    sym = fmt.symbol_for_column(snap["value_column"])
    last, prev, first = vals[-1], (vals[-2] if len(vals) > 1 else vals[-1]), vals[0]
    delta_v = ((last - prev) / prev * 100) if prev else 0.0
    delta_tot = ((last - first) / first * 100) if first else 0.0

    kpi_children = [
        kpi_card(
            f"Valor total · {snap['value_label']}",
            fmt.fmt_money(last, sym),
            delta=fmt.fmt_signed(delta_v),
            delta_positive=delta_v >= 0,
            sub=f"{years[-1]} vs. {years[-2] if len(years) > 1 else years[-1]}",
            spark=basic.sparkline_svg(vals[-12:], color=basic.theme.YALE_BLUE),
        ),
    ]
    has_mass = "q_mass" in ov and ov["q_mass"].notna().any() and float(ov["q_mass"].sum()) > 0
    has_vol = "q_vol" in ov and ov["q_vol"].notna().any() and float(ov["q_vol"].sum()) > 0
    if has_mass:
        m = ov["q_mass"].tolist()
        kpi_children.append(
            kpi_card(
                "Quantidade · massa (t)",
                fmt.fmt_num(m[-1], "t"),
                sub=f"{years[-1]}",
                spark=basic.sparkline_svg(m[-12:], color=basic.theme.EMBRAPA_GREEN),
            )
        )
    if has_vol:
        vv = ov["q_vol"].tolist()
        kpi_children.append(
            kpi_card(
                "Quantidade · volume (m³)",
                fmt.fmt_num(vv[-1], "m³"),
                sub=f"{years[-1]}",
                spark=basic.sparkline_svg(vv[-12:], color="#3A74B0"),
            )
        )
    q = snap["quality"]
    if q is not None and not q.empty:
        ok = q[q["data_quality_flag"] == "OK"]
        ok_share = float(ok["share"].iloc[0]) if not ok.empty else 0.0
        kpi_children.append(
            kpi_card(
                "Linhas íntegras (OK)",
                fmt.fmt_pct(ok_share),
                sub=f"{fmt.fmt_rows(float(q['n_rows'].sum()))} linhas",
            )
        )
    kpis = html.Div(kpi_children, className="kpi-row")

    labels, comp_vals, colors = composition_latest(snap["product_ts"], snap["products"])
    hero = html.Div(
        [
            card(
                [
                    section_header(
                        f"Série histórica · {years[0]}–{years[-1]} · {snap['value_label']}",
                        f"Variação acumulada: {fmt.fmt_signed(delta_tot, 0)}",
                    ),
                    basic.line_area(years, vals, label=sym),
                ]
            ),
            card(
                [
                    section_header(f"Composição · {years[-1]}", "Participação por produto"),
                    basic.donut(labels, comp_vals, colors=colors)
                    if labels
                    else html.P(
                        "Sem produtos na seleção.",
                        className="caption",
                        style={"padding": "24px 4px", "textAlign": "center"},
                    ),
                ]
            ),
        ],
        className="grid-2",
    )

    blocks = [kpis, hero]

    uf = snap["uf_data"]
    has_geo = "geo" in banco.provides and uf is not None and not uf.empty
    digest_cards = []
    if has_geo:
        value_by_uf = dict(zip(uf["state_acronym"], uf["total_value"], strict=False))
        top3 = uf.sort_values("total_value", ascending=False).head(3)["state_acronym"].tolist()
        digest_cards.append(
            card(
                [
                    section_header(
                        f"Distribuição geográfica · {years[-1]}",
                        f"Valor por UF · {sym}",
                        action=html.Span("Top 3: " + " · ".join(top3), className="caption"),
                    ),
                    geocharts.brazil_tile_map(value_by_uf, label=sym),
                ]
            )
        )
    if q is not None and not q.empty:
        digest_cards.append(
            card(
                [
                    section_header(
                        "Qualidade dos dados · agregado",
                        "Distribuição de flags",
                        action=html.Span(f"{len(q)} flags", className="caption"),
                    ),
                    qa_rows(q.sort_values("n_rows", ascending=False)),
                ]
            )
        )
    if digest_cards:
        blocks.append(html.Div(digest_cards, className="grid-2"))
    return blocks
