"""Plotly template — the Embrapa visual identity applied to every figure.

Anchored on the Presentations palette (Yale Blue + grays) for chart legibility
on white. Colorway = the eight --viz-* tokens from 01-tokens.css.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

VIZ_COLORS = [
    "#1D4D7E",  # --viz-1 yale blue
    "#006f35",  # --viz-2 embrapa green
    "#B7791F",  # --viz-3 amber
    "#3A74B0",  # --viz-4 french blue
    "#6e867d",  # --viz-5 gray-green
    "#B23A2B",  # --viz-6 terracotta
    "#0e3b65",  # --viz-7 deep navy
    "#B4D0E7",  # --viz-8 beau blue
]

FONT_FAMILY = "Univers, 'Embrapa Verdana', 'Helvetica Neue', Arial, sans-serif"
FG_PRIMARY = "#1a1f1c"
FG_SECONDARY = "#666666"
GRID_COLOR = "rgba(0,60,29,0.08)"
AXIS_COLOR = "rgba(0,60,29,0.14)"

EMBRAPA_TEMPLATE = go.layout.Template(
    layout=dict(
        font=dict(family=FONT_FAMILY, size=13, color=FG_PRIMARY),
        colorway=VIZ_COLORS,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        xaxis=dict(
            showgrid=False,
            linecolor=AXIS_COLOR,
            ticks="outside",
            ticklen=4,
            tickcolor=AXIS_COLOR,
            tickfont=dict(size=11, color=FG_SECONDARY),
            title=dict(font=dict(size=11, color=FG_SECONDARY)),
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID_COLOR,
            linecolor=AXIS_COLOR,
            tickfont=dict(size=11, color=FG_SECONDARY),
            title=dict(font=dict(size=11, color=FG_SECONDARY)),
            zerolinecolor=AXIS_COLOR,
        ),
        margin=dict(l=56, r=16, t=16, b=40),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor=AXIS_COLOR,
            font=dict(family=FONT_FAMILY, size=12, color=FG_PRIMARY),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(size=11, color=FG_SECONDARY),
            bgcolor="rgba(255,255,255,0)",
        ),
        separators=",.",
    )
)


def install_template() -> None:
    """Register the template as the global default. Safe to call multiple times."""
    pio.templates["embrapa"] = EMBRAPA_TEMPLATE
    pio.templates.default = "embrapa"
