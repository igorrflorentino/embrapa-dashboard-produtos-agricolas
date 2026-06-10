"""Cross-source Plotly charts: dual-axis overlay and stacked per-series panels."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc
from plotly.subplots import make_subplots

from .. import theme

_CONFIG = {"displayModeBar": False, "responsive": True}


def _rgba(color: str, alpha: float) -> str:
    if not color.startswith("#") or len(color) != 7:
        return color
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def dual_axis(series, *, height: int = 320) -> dcc.Graph:
    """Up to two distinct units, each on its own Y axis (left = 1st unit, right = 2nd)."""
    units = list(dict.fromkeys(s["unit"] for s in series))
    right = units[1] if len(units) > 1 else None
    fig = go.Figure()
    for s in series:
        on_right = right is not None and s["unit"] == right
        fig.add_scatter(
            x=[p["y"] for p in s["points"]],
            y=[p["v"] for p in s["points"]],
            mode="lines",
            name=f"{s['label']} · {s['banco_short']}",
            line=dict(color=s["color"], width=2.25),
            yaxis="y2" if on_right else "y",
            hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
        )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height,
        margin=dict(l=56, r=60, t=28, b=30),
        yaxis=dict(title=units[0] if units else ""),
        yaxis2=dict(title=right or "", overlaying="y", side="right", showgrid=False),
    )
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")


def stacked_panels(series, *, panel_height: int = 120) -> dcc.Graph:
    """One synced mini-panel per series — faithful native units, shared year axis."""
    n = max(len(series), 1)
    titles = [f"{s['label']} · {s['banco_short']} ({s['unit']})" for s in series]
    fig = make_subplots(
        rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.07, subplot_titles=titles
    )
    for i, s in enumerate(series, start=1):
        fig.add_scatter(
            x=[p["y"] for p in s["points"]],
            y=[p["v"] for p in s["points"]],
            mode="lines",
            line=dict(color=s["color"], width=2),
            fill="tozeroy",
            fillcolor=_rgba(s["color"], 0.10),
            name=s["label"],
            row=i,
            col=1,
            hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
        )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=max(panel_height * n + 40, 200),
        margin=dict(l=56, r=14, t=28, b=28),
        showlegend=False,
    )
    fig.update_annotations(font=dict(size=12, color=theme.FG_2))
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")
