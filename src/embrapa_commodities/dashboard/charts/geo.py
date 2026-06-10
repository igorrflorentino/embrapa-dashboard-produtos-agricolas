"""Geographic charts — the Brazil hex/tile-map and region bars.

The tile-map's ``(col, row)`` grid is the design system's hand-authored hex
layout (``data.js`` ``UF_DATA``), copied verbatim per the contract ("do not
reinvent the grid"). Real per-UF values come from BigQuery; this module only
places each UF at its design position and colours it on the institutional heat
ramp.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc

from .. import theme

_CONFIG = {"displayModeBar": False, "responsive": True}

# UF → (column, row, region, full name). Verbatim from the prototype's UF_DATA
# tile-map grid (27 federative units on Brazil's hexagonal layout).
UF_GRID: dict[str, dict] = {
    "RR": {"col": 3, "row": 0, "region": "N", "name": "Roraima"},
    "AP": {"col": 5, "row": 0, "region": "N", "name": "Amapá"},
    "AM": {"col": 2, "row": 1, "region": "N", "name": "Amazonas"},
    "PA": {"col": 4, "row": 1, "region": "N", "name": "Pará"},
    "AC": {"col": 1, "row": 2, "region": "N", "name": "Acre"},
    "RO": {"col": 2, "row": 2, "region": "N", "name": "Rondônia"},
    "TO": {"col": 4, "row": 2, "region": "N", "name": "Tocantins"},
    "MA": {"col": 5, "row": 1, "region": "NE", "name": "Maranhão"},
    "CE": {"col": 6, "row": 1, "region": "NE", "name": "Ceará"},
    "RN": {"col": 7, "row": 1, "region": "NE", "name": "Rio Grande do Norte"},
    "PI": {"col": 5, "row": 2, "region": "NE", "name": "Piauí"},
    "PB": {"col": 7, "row": 2, "region": "NE", "name": "Paraíba"},
    "BA": {"col": 5, "row": 3, "region": "NE", "name": "Bahia"},
    "PE": {"col": 6, "row": 3, "region": "NE", "name": "Pernambuco"},
    "AL": {"col": 6, "row": 4, "region": "NE", "name": "Alagoas"},
    "SE": {"col": 5, "row": 5, "region": "NE", "name": "Sergipe"},
    "MT": {"col": 3, "row": 3, "region": "CO", "name": "Mato Grosso"},
    "MS": {"col": 3, "row": 4, "region": "CO", "name": "Mato Grosso do Sul"},
    "GO": {"col": 4, "row": 4, "region": "CO", "name": "Goiás"},
    "DF": {"col": 4, "row": 5, "region": "CO", "name": "Distrito Federal"},
    "MG": {"col": 5, "row": 4, "region": "SE", "name": "Minas Gerais"},
    "ES": {"col": 6, "row": 5, "region": "SE", "name": "Espírito Santo"},
    "RJ": {"col": 5, "row": 6, "region": "SE", "name": "Rio de Janeiro"},
    "SP": {"col": 4, "row": 6, "region": "SE", "name": "São Paulo"},
    "PR": {"col": 3, "row": 6, "region": "S", "name": "Paraná"},
    "SC": {"col": 3, "row": 7, "region": "S", "name": "Santa Catarina"},
    "RS": {"col": 3, "row": 8, "region": "S", "name": "Rio Grande do Sul"},
}

REGION_LABEL = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}


def brazil_tile_map(
    value_by_uf: dict[str, float], *, label: str = "Valor", height: int = 320
) -> dcc.Graph:
    """Hex tile-map of Brazil's 27 UFs coloured by value on the heat ramp."""
    ufs = list(UF_GRID)
    xs = [UF_GRID[u]["col"] for u in ufs]
    ys = [-UF_GRID[u]["row"] for u in ufs]  # negative → row 0 at the top
    vals = [float(value_by_uf.get(u, 0) or 0) for u in ufs]
    names = [UF_GRID[u]["name"] for u in ufs]
    fig = go.Figure(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            text=ufs,
            textposition="middle center",
            textfont=dict(size=11, color=theme.FG_1),
            marker=dict(
                symbol="square",
                size=34,
                line=dict(color="#fff", width=2),
                color=vals,
                colorscale=theme.heat_colorscale(),
                colorbar=dict(
                    title=dict(text=label, side="right"), thickness=10, len=0.85, outlinewidth=0
                ),
                cmin=0,
            ),
            customdata=list(zip(names, vals, strict=False)),
            hovertemplate="%{customdata[0]} (%{text})<br>%{customdata[1]:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
    )
    fig.update_xaxes(visible=False, range=[0, 8])
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1, range=[-8.6, 0.6])
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")


def region_bars(
    region_totals: dict[str, float], *, label: str = "Valor", height: int = 220
) -> dcc.Graph:
    """Value by macro-region, coloured with the region palette."""
    order = ["N", "NE", "CO", "SE", "S"]
    present = [r for r in order if r in region_totals]
    labels = [REGION_LABEL[r] for r in present]
    values = [region_totals[r] for r in present]
    colors = [theme.REGION_COLOR[r] for r in present]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors),
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height,
        showlegend=False,
        xaxis_title=label,
        margin=dict(l=8, r=16, t=12, b=28),
    )
    fig.update_yaxes(autorange="reversed")
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")
