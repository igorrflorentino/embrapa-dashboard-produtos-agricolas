"""Geografia — territorial distribution: tile-map, regions, UF ranking."""

from __future__ import annotations

from dash import html

from .. import format as fmt
from .. import seam
from ..charts import basic
from ..charts import geo as geocharts
from ..components.cards import card, kpi_card, section_header
from ._helpers import top_n_share


def layout(banco_id: str, conv: dict, summary: dict | None = None) -> list:
    snap = seam.snapshot(banco_id, conv, summary)
    uf = snap["uf_data"]
    if uf is None or uf.empty:
        return [
            card(
                html.P(
                    "Este banco não expõe dimensão geográfica (UF).",
                    className="caption",
                    style={"padding": "24px 4px"},
                ),
                subtle=True,
            )
        ]
    uf = uf[uf["total_value"].notna()].sort_values("total_value", ascending=False)
    sym = fmt.symbol_for_column(snap["value_column"])
    value_by_uf = dict(zip(uf["state_acronym"], uf["total_value"], strict=False))
    covered = int((uf["total_value"] > 0).sum())
    leader = uf.iloc[0]
    top3 = top_n_share(uf["total_value"].tolist(), 3)

    region_totals: dict[str, float] = {}
    if "region_abbrev" in uf.columns:
        grp = uf.dropna(subset=["region_abbrev"]).groupby("region_abbrev")["total_value"].sum()
        region_totals = {k: float(v) for k, v in grp.items()}
    region_leader = max(region_totals, key=region_totals.get) if region_totals else "—"

    kpis = html.Div(
        [
            kpi_card("UFs com produção", f"{covered} / 27", sub="unidades federativas"),
            kpi_card(
                "UF líder", str(leader["state_acronym"]), sub=str(leader.get("state_name", ""))
            ),
            kpi_card(
                "Concentração (top 3)", fmt.fmt_pct(top3), sub="participação das 3 maiores UFs"
            ),
            kpi_card(
                "Região líder",
                geocharts.REGION_LABEL.get(region_leader, region_leader),
                sub="maior valor agregado",
            ),
        ],
        className="kpi-row",
    )

    grid = html.Div(
        [
            card(
                [
                    section_header(f"Mapa por UF · {sym}", "Distribuição territorial do valor"),
                    geocharts.brazil_tile_map(value_by_uf, label=sym),
                ]
            ),
            card(
                [
                    section_header("Por região", "Valor agregado por macrorregião"),
                    geocharts.region_bars(region_totals, label=sym),
                ]
            ),
        ],
        className="grid-2",
    )

    rank = uf.head(14)
    ranking = card(
        [
            section_header(
                "Ranking de UFs",
                f"Maiores produtores · {sym}",
                action=html.Span(f"{covered} UFs", className="caption"),
            ),
            basic.bar_h(
                rank["state_acronym"].tolist(), rank["total_value"].tolist(), label=sym, height=320
            ),
        ]
    )
    return [kpis, grid, ranking]
