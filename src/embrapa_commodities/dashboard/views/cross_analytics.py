"""Cross-source analytics (Multi-fonte) — export coefficient, world market share,
farm-gate vs FOB price, and trade mirror. Each maps one commodity across bancos
via the crosswalk (``seam.*`` builders) and reads the shared ``ui['cross_product']``
selection set by the commodity picker.
"""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..charts import geo as geocharts
from ..components.cards import card, kpi_card, section_header
from ..theme import EMBRAPA_GREEN, YALE_BLUE


def _pct(v: float | None, decimals: int = 1) -> str:
    """Format an already-percentage value (0–100) — not a 0–1 fraction."""
    return "—" if v is None else fmt.fmt_num(v, decimals=decimals) + "%"


def commodity_picker(selected: str | None) -> html.Div:
    """Single-select commodity chips (the crosswalk commodities + 'cesta completa')."""
    chips = [
        html.Button(
            "Cesta completa",
            className="pp-chip" + (" on" if not selected else ""),
            id={"type": "xproduct", "code": "__all__"},
            n_clicks=0,
        )
    ]
    for cid, c in seam.commodity_catalog().items():
        chips.append(
            html.Button(
                c["name"],
                className="pp-chip" + (" on" if selected == cid else ""),
                id={"type": "xproduct", "code": cid},
                n_clicks=0,
                title=cid,
            )
        )
    return html.Div(
        [
            html.Span("Commodity", className="pp-selector-label"),
            html.Div(chips, className="pp-chips"),
        ],
        className="pp-selector",
    )


def _empty(msg: str) -> list:
    return [card(html.P(msg, className="caption", style={"padding": "24px 4px"}), subtle=True)]


# ── (1) Coeficiente de exportação — PEVS × COMEX, by UF ──────────────────────
def export_coef(ui: dict) -> list:
    prod = ui.get("cross_product")
    data = seam.export_coefficient(prod)
    ranked = sorted(
        (u for u in data["by_uf"] if u["production"] > 0), key=lambda u: u["coefPct"], reverse=True
    )
    picker = commodity_picker(prod)
    if not ranked:
        return [picker, *_empty("Sem produção/exportação cruzável para esta commodity.")]
    top_vol = max(ranked, key=lambda u: u["exportV"])  # who ships most, by volume
    bottom = min(ranked, key=lambda u: u["coefPct"])  # least export-oriented producer
    nat = data["national"]
    kpis = html.Div(
        [
            kpi_card(
                "Coeficiente nacional", _pct(nat["coefPct"]), sub="do produzido segue p/ exportação"
            ),
            kpi_card(
                "Maior volume embarcado",
                top_vol["uf"],
                sub=f"{fmt.fmt_num(top_vol['exportV'], decimals=1)} mil t exportadas",
            ),
            kpi_card("UF mais interna", bottom["uf"], sub=f"{_pct(bottom['coefPct'])} exportado"),
            kpi_card(
                "Produção considerada",
                fmt.fmt_num(nat["production"], decimals=1) + " mil t",
                sub=f"{len(ranked)} UF{'s' if len(ranked) != 1 else ''} com produção",
            ),
        ],
        className="kpi-row",
    )
    # Map colour saturates at 100%: SECEX books exports to the shipping UF, so
    # logistics/processing hubs can exceed local production. Real values stay in the table.
    map_by_uf = {u["uf"]: min(100.0, u["coefPct"]) for u in data["by_uf"]}
    ts = data["timeseries"]
    blocks = [
        picker,
        kpis,
        card(
            [
                section_header(
                    "Orientação exportadora · por UF",
                    "Quanto da produção de cada estado vai para fora",
                    action=html.Span("% exportado · IBGE × MDIC", className="caption"),
                ),
                geocharts.brazil_tile_map(map_by_uf, label="% exp."),
                html.P(
                    "A SECEX (MDIC) atribui a exportação à UF de embarque, não à de "
                    "produção; polos logísticos podem assim superar a própria produção "
                    "(a cor satura em 100%). O coeficiente nacional é a medida robusta.",
                    className="caption",
                    style={"padding": "10px 2px 2px"},
                ),
            ]
        ),
    ]
    if ts:
        blocks.append(
            card(
                [
                    section_header(
                        "Coeficiente nacional no tempo", "Evolução da orientação exportadora"
                    ),
                    basic.line_area(
                        [d["y"] for d in ts], [d["v"] for d in ts], label="%", color=EMBRAPA_GREEN
                    ),
                ]
            )
        )
    rows = [
        html.Tr(
            [
                html.Td([u["name"], html.Small(f" {u['uf']}", style={"color": "var(--fg-3)"})]),
                html.Td(fmt.fmt_num(u["production"], decimals=1), className="num tnum"),
                html.Td(fmt.fmt_num(u["exportV"], decimals=1), className="num tnum"),
                html.Td(_pct(u["coefPct"]), className="num tnum"),
            ]
        )
        for u in sorted(ranked, key=lambda u: u["exportV"], reverse=True)[:10]
    ]
    blocks.append(
        card(
            [
                section_header("Ranking · maior volume exportado", "UFs por volume embarcado"),
                html.Div(
                    html.Table(
                        [
                            html.Thead(
                                html.Tr(
                                    [
                                        html.Th("UF"),
                                        html.Th("Produção (mil t)", className="num"),
                                        html.Th("Exportado (mil t)", className="num"),
                                        html.Th("Coeficiente", className="num"),
                                    ]
                                )
                            ),
                            html.Tbody(rows),
                        ],
                        className="pc-table",
                    ),
                    className="pc-table-wrap",
                ),
            ]
        )
    )
    return blocks


# ── (2) Brasil no mercado mundial — COMEX × COMTRADE ─────────────────────────
def market_share(ui: dict) -> list:
    prod = ui.get("cross_product")
    data = seam.market_share(prod)
    picker = commodity_picker(prod)
    series = data["series"]
    if not series:
        return [picker, *_empty("Sem janela comparável MDIC × Comtrade para esta commodity.")]
    last, first = series[-1], series[0]
    peak = max(series, key=lambda d: d["share"])
    kpis = html.Div(
        [
            kpi_card(
                "Participação atual", _pct(last["share"]), sub=f"{last['y']} · do mercado mundial"
            ),
            kpi_card("Pico histórico", _pct(peak["share"]), sub=f"em {peak['y']}"),
            kpi_card(
                "Variação na janela",
                fmt.fmt_signed(last["share"] - first["share"], 1, " p.p."),
                delta_positive=last["share"] >= first["share"],
                sub=f"{first['y']}–{last['y']}",
            ),
            kpi_card(
                "Exportação BR",
                fmt.fmt_money(last["br"] * 1e9, "US$"),
                sub=f"mundo: {fmt.fmt_money(last['world'] * 1e9, 'US$')}",
            ),
        ],
        className="kpi-row",
    )
    blocks = [
        picker,
        kpis,
        card(
            [
                section_header(
                    "Participação no mercado mundial",
                    "Fração brasileira da exportação global",
                    action=html.Span("% · MDIC ÷ UN Comtrade", className="caption"),
                ),
                basic.line_area(
                    [d["y"] for d in series],
                    [d["share"] for d in series],
                    label="% do mundo",
                    color=YALE_BLUE,
                ),
            ]
        ),
    ]
    bp = data["by_product"]
    if bp:
        blocks.append(
            card(
                [
                    section_header(
                        "Participação por commodity · último ano",
                        "Onde o Brasil pesa mais no mundo",
                    ),
                    basic.bar_h(
                        [p["name"] for p in bp], [p["share"] for p in bp], label="% do mundo"
                    ),
                ]
            )
        )
    return blocks


# ── (3) Preço: porteira vs. FOB — PEVS × COMEX ───────────────────────────────
def price_spread(ui: dict) -> list:
    prod = ui.get("cross_product")
    data = seam.price_spread(prod)
    picker = commodity_picker(prod)
    series = data["series"]
    if not series:
        return [picker, *_empty("Sem preços cruzáveis (porteira × FOB) para esta commodity.")]
    last = series[-1]
    kpis = html.Div(
        [
            kpi_card(
                "Preço FOB atual",
                fmt.fmt_money(last["fob"], "US$", compact=False) + "/kg",
                sub=f"{last['y']} · no porto",
            ),
            kpi_card(
                "Preço na porteira",
                fmt.fmt_money(last["gate"], "US$", compact=False) + "/kg",
                sub="na produção",
            ),
            kpi_card("Markup", "×" + fmt.fmt_num(last["markup"], decimals=1), sub="FOB ÷ porteira"),
            kpi_card(
                "Spread",
                fmt.fmt_money(last["spread"], "US$", compact=False) + "/kg",
                sub="valor agregado porteira → porto",
            ),
        ],
        className="kpi-row",
    )
    line = basic.multi_line(
        [
            {
                "name": "Preço de exportação (FOB)",
                "color": "#B7791F",
                "xs": [d["y"] for d in series],
                "ys": [d["fob"] for d in series],
            },
            {
                "name": "Preço na porteira (produção)",
                "color": EMBRAPA_GREEN,
                "xs": [d["y"] for d in series],
                "ys": [d["gate"] for d in series],
            },
        ],
        label="US$/kg",
        height=300,
    )
    markup = basic.line_area(
        [d["y"] for d in series], [d["markup"] for d in series], label="×", color="#06617c"
    )
    return [
        picker,
        kpis,
        card(
            [
                section_header(
                    "Porteira vs. porto · US$/kg",
                    "Onde o valor é capturado",
                    action=html.Span("IBGE × MDIC", className="caption"),
                ),
                line,
            ]
        ),
        card([section_header("Markup no tempo", "Quantas vezes o porto vale a porteira"), markup]),
    ]


# ── (4) Espelho comercial — COMEX × COMTRADE ─────────────────────────────────
def mirror(ui: dict) -> list:
    prod = ui.get("cross_product")
    data = seam.trade_mirror(prod)
    picker = commodity_picker(prod)
    series, disc = data["series"], data["discrepancy"]
    if not series:
        return [picker, *_empty("Sem janela comparável MDIC × Comtrade para esta commodity.")]
    last = series[-1]
    avg_disc = sum(d["v"] for d in disc) / len(disc) if disc else 0
    kpis = html.Div(
        [
            kpi_card("Divergência média", _pct(avg_disc), sub="entre MDIC e Comtrade"),
            kpi_card(
                "Exportação MDIC", fmt.fmt_money(last["mdic"] * 1e9, "US$"), sub=f"{last['y']}"
            ),
            kpi_card(
                "Exportação Comtrade",
                fmt.fmt_money(last["comtrade"] * 1e9, "US$"),
                sub=f"{last['y']} · reporter Brasil",
            ),
            kpi_card(
                "Janela comparável", f"{series[0]['y']}–{last['y']}", sub="anos em ambas as fontes"
            ),
        ],
        className="kpi-row",
    )
    line = basic.multi_line(
        [
            {
                "name": "MDIC · SECEX",
                "color": YALE_BLUE,
                "xs": [d["y"] for d in series],
                "ys": [d["mdic"] for d in series],
            },
            {
                "name": "UN Comtrade (Brasil)",
                "color": "#B7791F",
                "xs": [d["y"] for d in series],
                "ys": [d["comtrade"] for d in series],
            },
        ],
        label="US$ bi",
        height=300,
    )
    return [
        picker,
        kpis,
        card(
            [
                section_header(
                    "A mesma exportação, duas fontes",
                    "MDIC × Comtrade",
                    action=html.Span("US$ bi · reporter Brasil", className="caption"),
                ),
                line,
            ]
        ),
        card(
            [
                section_header(
                    "Divergência no tempo",
                    "Quão distantes estão as fontes",
                    action=html.Span("% · |MDIC − Comtrade| ÷ média", className="caption"),
                ),
                basic.line_area(
                    [d["y"] for d in disc],
                    [d["v"] for d in disc],
                    label="% diverg.",
                    color="#B7791F",
                ),
                html.P(
                    "Divergências apontam diferenças de metodologia, defasagem de revisão ou "
                    "cobertura — um diagnóstico que nenhuma fonte isolada revela.",
                    className="caption",
                    style={"padding": "10px 2px 2px"},
                ),
            ]
        ),
    ]
