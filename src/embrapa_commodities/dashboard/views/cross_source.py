"""Cruzamento entre fontes — compare 2-4 annual series across bancos (Multi-fonte).

Reads the cross-state from the ``ui`` store ({series:[{b,m}], mode}); the picker
chips and mode toggle write back through the app's state callback. All data flows
through ``seam.cross_series`` — series from different bancos plotted on one axis.
"""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..charts import cross as crosscharts
from ..components.cards import card, kpi_card, section_header
from ..components.icons import icon
from ._helpers import accum_pct, cagr

CS_COLORS = ["#1D4D7E", "#B7791F", "#7B5898", "#2A8B6C"]
_FAMILY_LABEL = {
    "currency": "valor monetário",
    "mass": "massa",
    "volume": "volume",
    "ratio": "razão / índice",
    "area": "área",
    "rendimento": "rendimento",
}
DEFAULT_CROSS = {
    "series": [{"b": "ibge_pevs", "m": "prod_value"}, {"b": "mdic_comex", "m": "exp_value"}],
    "mode": "base100",
}


def layout(ui: dict) -> list:
    cross = ui.get("cross") or DEFAULT_CROSS
    refs = cross.get("series") or DEFAULT_CROSS["series"]
    mode = cross.get("mode", "base100")
    y0, y1 = seam.cross_common_window(refs)

    results = []
    for i, r in enumerate(refs):
        s = seam.cross_series(r["b"], r["m"], y0, y1)
        if s:
            s["color"] = CS_COLORS[i % len(CS_COLORS)]
            results.append(s)
    units = list(dict.fromkeys(s["unit"] for s in results))
    families = list(dict.fromkeys(s["family"] for s in results))
    n_bancos = len({s["banco"] for s in results})

    kpis = html.Div(
        [
            kpi_card(
                "Séries comparadas",
                f"{len(results)} / 4",
                sub=f"de {n_bancos} banco{'s' if n_bancos != 1 else ''}",
            ),
            kpi_card("Janela comparável", f"{y0}–{y1}", sub="interseção das coberturas"),
            kpi_card(
                "Famílias de unidade",
                str(len(families)),
                sub=" · ".join(_FAMILY_LABEL.get(f, f) for f in families) or "—",
            ),
            kpi_card("Unidades", str(len(units)), sub=" · ".join(units) or "—"),
        ],
        className="kpi-row",
    )

    selected = {(r["b"], r["m"]) for r in refs}
    return [kpis, _picker(selected), _chart_card(results, mode, y0), _table_card(results, y0, y1)]


def _picker(selected: set) -> html.Div:
    by_banco: dict = {}
    for ref in seam.cross_metric_refs():
        by_banco.setdefault(ref["banco"], []).append(ref)
    banks = []
    for bid, metrics in by_banco.items():
        chips = [
            html.Button(
                [
                    html.Span(m["label"], className="xs-chip-label"),
                    html.Span(
                        seam.CROSS_DISPLAY_UNIT.get(f"{bid}:{m['metric']}", ""),
                        className="xs-chip-unit tnum",
                    ),
                ],
                className="xs-chip" + (" on" if (bid, m["metric"]) in selected else ""),
                id={"type": "xmetric", "banco": bid, "metric": m["metric"]},
                n_clicks=0,
            )
            for m in metrics
        ]
        banks.append(
            html.Div(
                [
                    html.Div(
                        [
                            icon("database", size=14, color="#333333"),
                            html.Span(metrics[0]["banco_short"], className="xs-bank-short"),
                        ],
                        className="xs-bank-head",
                    ),
                    html.Div(chips, className="xs-bank-metrics"),
                ],
                className="xs-bank",
            )
        )
    return card(
        [
            section_header(
                "Montagem do cruzamento",
                "Selecione as séries a comparar",
                action=html.Span(f"{len(selected)} de 4 · mín. 1", className="caption"),
            ),
            html.Div(banks, className="xs-picker"),
        ]
    )


def _chart_card(results: list, mode: str, y0: int) -> html.Div:
    seg = html.Div(
        [
            html.Button(
                lbl,
                className="seg-opt" + (" on" if mode == v else ""),
                id={"type": "xmode", "value": v},
                n_clicks=0,
            )
            for v, lbl in (("base100", "Base 100"), ("dual", "Eixo duplo"), ("panels", "Painéis"))
        ],
        className="seg xs-seg",
    )

    if not results:
        chart = html.P(
            "Selecione ao menos uma série.", className="caption", style={"padding": "24px 4px"}
        )
    elif mode == "base100":
        series = []
        for s in results:
            pts = s["points"]
            v0 = pts[0]["v"] if pts else 0
            series.append(
                {
                    "name": f"{s['label']} · {s['banco_short']}",
                    "color": s["color"],
                    "xs": [p["y"] for p in pts],
                    "ys": [(p["v"] / v0 * 100 if v0 else 0) for p in pts],
                }
            )
        chart = basic.multi_line(series, label=f"índice ({y0}=100)", height=320)
    elif mode == "dual":
        chart = crosscharts.dual_axis(results)
    else:
        chart = crosscharts.stacked_panels(results)

    legend = html.Div(
        [
            html.Span(
                [
                    html.Span(className="xs-legend-dot", style={"background": s["color"]}),
                    html.Strong(s["label"]),
                    html.Span(f"{s['banco_short']} · {s['unit']}", className="xs-legend-src"),
                ],
                className="xs-legend-item",
            )
            for s in results
        ],
        className="xs-legend",
    )
    return card(
        [
            section_header("Sobreposição no tempo", "Evolução histórica comparada", action=seg),
            chart,
            legend,
        ]
    )


def _table_card(results: list, y0: int, y1: int) -> html.Div:
    rows = []
    for s in results:
        pts = s["points"]
        v0 = pts[0]["v"] if pts else 0
        vt = pts[-1]["v"] if pts else 0
        ac, cg = accum_pct(v0, vt), (cagr(v0, vt, len(pts) - 1) if len(pts) > 1 else None)
        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Span(className="pc-row-dot", style={"background": s["color"]}),
                            s["label"],
                        ]
                    ),
                    html.Td(s["banco_short"]),
                    html.Td(f"{fmt.fmt_num(v0, decimals=1)} {s['unit']}", className="num tnum"),
                    html.Td(f"{fmt.fmt_num(vt, decimals=1)} {s['unit']}", className="num tnum"),
                    html.Td(fmt.fmt_signed(ac, 0) if ac is not None else "—", className="num tnum"),
                    html.Td(fmt.fmt_signed(cg, 1) if cg is not None else "—", className="num tnum"),
                ]
            )
        )
    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Série"),
                        html.Th("Fonte"),
                        html.Th(str(y0), className="num"),
                        html.Th(str(y1), className="num"),
                        html.Th("Variação acum.", className="num"),
                        html.Th("CAGR (a.a.)", className="num"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="pc-table",
    )
    return card(
        [
            section_header(
                f"Métricas comparativas · {y0}–{y1}", "Crescimento de cada série na janela"
            ),
            html.Div(table, className="pc-table-wrap"),
        ]
    )
