"""The ``embrapa`` Plotly template + the design-system palette.

Mirrors the tokens in ``assets/colors_and_type.css`` so every figure shares the
brand's data-surface palette and typography. Critical brand rule (README §
"two palettes"): the **presentations** palette + the ``--viz-*`` ramp deliver
data; corporate green (``#006f35``) is chrome only — so the categorical colorway
here leads with Yale blue, not green.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand tokens (hex mirror of colors_and_type.css) ─────────────────────────
EMBRAPA_GREEN = "#006f35"
EMBRAPA_GREEN_DARKER = "#003c1d"
EMBRAPA_BLUE = "#06617c"
YALE_BLUE = "#1D4D7E"

FG_1 = "#1a1f1c"
FG_2 = "#333333"
FG_3 = "#666666"
FG_4 = "#9aa5a0"
SURFACE = "#FFFFFF"
BORDER_SUBTLE = "rgba(0, 60, 29, 0.08)"
BORDER_DEFAULT = "rgba(0, 60, 29, 0.14)"

OK = EMBRAPA_GREEN
WARN = "#B7791F"
ERR = "#B23A2B"
INFO = EMBRAPA_BLUE

# Categorical data-viz scale (--viz-1 … --viz-10). Yale blue first (data, not chrome).
VIZ_SCALE = [
    "#1D4D7E",  # yale blue
    "#006f35",  # embrapa green
    "#B7791F",  # amber
    "#3A74B0",  # french blue
    "#6e867d",  # gray-green
    "#B23A2B",  # terracotta
    "#0e3b65",  # deep navy
    "#B4D0E7",  # beau blue
    "#7B5898",  # purple
    "#2A8B6C",  # teal-green
]

# Sequential green "heat" ramp (--heat-0 … --heat-7) for tile-maps and heatmaps.
HEAT_SCALE = [
    "#F3F4F1",
    "#EEF4EE",
    "#CFE4D6",
    "#9FCEBB",
    "#5FB295",
    "#2A8B6C",
    "#006F35",
    "#003E1C",
]


def heat_colorscale() -> list[list]:
    """Plotly colorscale (0..1 stops) from the institutional heat ramp."""
    n = len(HEAT_SCALE)
    return [[i / (n - 1), c] for i, c in enumerate(HEAT_SCALE)]


# Region palette (matches data.js REGIONS → viz tokens).
REGION_COLOR = {
    "N": "#1D4D7E",
    "NE": "#B7791F",
    "CO": "#6e867d",
    "SE": "#006f35",
    "S": "#3A74B0",
}

FONT_BODY = "'Univers', 'Embrapa Verdana', 'Embrapa Arial', 'Helvetica Neue', Arial, sans-serif"

TEMPLATE_NAME = "embrapa"


def register_template() -> None:
    """Register the ``embrapa`` Plotly template (idempotent)."""
    if TEMPLATE_NAME in pio.templates:
        return
    axis = dict(
        gridcolor=BORDER_SUBTLE,
        zeroline=False,
        linecolor=BORDER_DEFAULT,
        ticks="outside",
        tickcolor=BORDER_DEFAULT,
        ticklen=4,
        tickfont=dict(size=11, color=FG_3),
        title=dict(font=dict(size=12, color=FG_3)),
        automargin=True,
    )
    template = go.layout.Template(
        layout=dict(
            font=dict(family=FONT_BODY, size=13, color=FG_2),
            colorway=VIZ_SCALE,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=48, r=16, t=16, b=36),
            xaxis=axis,
            yaxis=axis,
            hoverlabel=dict(
                bgcolor=SURFACE,
                bordercolor=BORDER_DEFAULT,
                font=dict(family=FONT_BODY, size=12, color=FG_1),
            ),
            legend=dict(
                font=dict(size=12, color=FG_2),
                bgcolor="rgba(0,0,0,0)",
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            colorscale=dict(sequential=heat_colorscale()),
            title=dict(font=dict(family=FONT_BODY, size=15, color=FG_1)),
        )
    )
    pio.templates[TEMPLATE_NAME] = template


register_template()
