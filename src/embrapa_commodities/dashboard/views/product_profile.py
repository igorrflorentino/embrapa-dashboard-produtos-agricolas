"""Perfil do produto — deep dive on a single commodity (M1: the top one by value)."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..components.cards import card, kpi_card, section_header
from ..registries import banco_by_id


def _col_map(products, col: str) -> dict:
    if products is None or products.empty:
        return {}
    return dict(zip(products["code"], products[col], strict=False))


def _ficha(code: str, unit: str, family: str, n_years: int) -> html.Dl:
    rows = [
        ("Código", html.Code(code)),
        ("Unidade nativa", unit or "—"),
        ("Família de unidade", family or "—"),
        ("Anos cobertos", str(n_years)),
    ]
    out = []
    for dt, dd in rows:
        out += [html.Dt(dt), html.Dd(dd)]
    return html.Dl(out, className="cs-cov")


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    banco = banco_by_id(banco_id)
    snap = seam.snapshot(banco_id, conv, summary)
    pts, products = snap["product_ts"], snap["products"]
    if pts is None or pts.empty:
        return [
            card(
                html.P(
                    "Sem séries de produto para a seleção atual.",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    last_year = int(pts["reference_year"].max())
    latest = pts[pts["reference_year"] == last_year].groupby("code")["total_value"].sum()
    code = str(latest.sort_values(ascending=False).index[0])
    name_by = _col_map(products, "name")
    unit_by = _col_map(products, "unit_native")
    fam_by = _col_map(products, "family")
    name = name_by.get(code, code)
    unit = unit_by.get(code, "")
    sym = fmt.symbol_for_column(snap["value_column"])

    s = pts[pts["code"] == code].sort_values("reference_year")
    years = s["reference_year"].tolist()
    vals = s["total_value"].tolist()
    qty = s["total_qty_native"].tolist()
    price_last = (vals[-1] / qty[-1]) if qty and qty[-1] else None
    price_str = (fmt.fmt_money(price_last, sym, compact=False) + f"/{unit}") if price_last else "—"
    basket_total = float(latest.sum())
    share = (float(latest.get(code, 0)) / basket_total) if basket_total else 0.0

    kpis = html.Div(
        [
            kpi_card(
                f"Valor · {snap['value_label']}",
                fmt.fmt_money(vals[-1], sym),
                sub=f"{name} · {years[-1]}",
                spark=basic.sparkline_svg(vals[-12:], color=basic.theme.YALE_BLUE),
            ),
            kpi_card(
                "Quantidade",
                fmt.fmt_num(qty[-1], unit),
                sub=f"{years[-1]}",
                spark=basic.sparkline_svg(qty[-12:], color=basic.theme.EMBRAPA_GREEN),
            ),
            kpi_card("Preço médio implícito", price_str, sub="valor ÷ quantidade"),
            kpi_card(
                "Participação na cesta",
                fmt.fmt_pct(share),
                sub=f"de {len(latest)} produtos · {last_year}",
            ),
        ],
        className="kpi-row",
    )

    grid1 = html.Div(
        [
            card(
                [
                    section_header(
                        f"Série de valor · {name}",
                        f"{years[0]}–{years[-1]} · {snap['value_label']}",
                    ),
                    basic.line_area(years, vals, label=sym),
                ]
            ),
            card(
                [
                    section_header("Ficha técnica", name),
                    _ficha(code, unit, fam_by.get(code, ""), len(years)),
                ]
            ),
        ],
        className="grid-2",
    )

    blocks = [kpis, grid1]
    rank = seam.product_uf_ranking(banco_id, code, conv, summary)
    qty_card = card(
        [
            section_header(f"Quantidade · {name}", f"Série anual ({unit})"),
            basic.line_area(years, qty, label=unit, color=basic.theme.EMBRAPA_GREEN),
        ]
    )
    if "geo" in banco.provides and rank is not None and not rank.empty:
        rank = (
            rank[rank["total_value"].notna()].sort_values("total_value", ascending=False).head(12)
        )
        blocks.append(
            html.Div(
                [
                    qty_card,
                    card(
                        [
                            section_header("Ranking de UFs", f"Onde {name} é produzido · {sym}"),
                            basic.bar_h(
                                rank["state_acronym"].tolist(),
                                rank["total_value"].tolist(),
                                label=sym,
                                height=300,
                            ),
                        ]
                    ),
                ],
                className="grid-2",
            )
        )
    else:
        blocks.append(qty_card)
    return blocks
