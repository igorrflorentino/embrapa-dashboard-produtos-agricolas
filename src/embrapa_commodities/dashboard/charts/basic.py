"""Core Plotly chart builders (line, bar, donut, multi-line, stacked, Lorenz)."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote

import plotly.graph_objects as go
from dash import dcc, html

from .. import theme

_CONFIG = {"displayModeBar": False, "responsive": True}


def _graph(fig: go.Figure, height: int) -> dcc.Graph:
    fig.update_layout(template=theme.TEMPLATE_NAME, height=height)
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")


def line_area(
    xs: Sequence, ys: Sequence, *, label: str = "", color: str = theme.YALE_BLUE, height: int = 240
) -> dcc.Graph:
    """Single value series as a line with a soft fill (backs série histórica)."""
    fig = go.Figure(
        go.Scatter(
            x=list(xs),
            y=list(ys),
            mode="lines",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.10),
            hovertemplate="%{x}: %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(yaxis_title=label, showlegend=False, margin=dict(l=56, r=12, t=12, b=28))
    fig.update_yaxes(rangemode="tozero")
    return _graph(fig, height)


def bar_h(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    color: str = theme.EMBRAPA_GREEN,
    label: str = "",
    height: int = 240,
) -> dcc.Graph:
    """Horizontal bar ranking (UFs, partners). Highest at top."""
    fig = go.Figure(
        go.Bar(
            x=list(values),
            y=list(labels),
            orientation="h",
            marker=dict(color=color),
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title=label, showlegend=False, margin=dict(l=8, r=16, t=12, b=28))
    fig.update_yaxes(autorange="reversed", ticksuffix="  ")
    return _graph(fig, height)


def donut(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    colors: Sequence[str] | None = None,
    height: int = 220,
) -> dcc.Graph:
    """Composition donut (participação por produto)."""
    fig = go.Figure(
        go.Pie(
            labels=list(labels),
            values=list(values),
            hole=0.62,
            sort=False,
            marker=dict(
                colors=list(colors) if colors else theme.VIZ_SCALE,
                line=dict(color="#fff", width=1.5),
            ),
            textinfo="percent",
            textposition="inside",
            insidetextorientation="horizontal",
            hovertemplate="%{label}: %{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        legend=dict(orientation="v", x=1.0, y=0.5, yanchor="middle", font=dict(size=12)),
    )
    return _graph(fig, height)


def multi_line(series: Sequence[dict], *, label: str = "", height: int = 280) -> dcc.Graph:
    """Several series on one axis. series=[{name, color, xs, ys}]."""
    fig = go.Figure()
    for i, s in enumerate(series):
        fig.add_scatter(
            x=list(s["xs"]),
            y=list(s["ys"]),
            mode="lines",
            name=s["name"],
            line=dict(color=s.get("color", theme.VIZ_SCALE[i % len(theme.VIZ_SCALE)]), width=2),
            hovertemplate=f"{s['name']} · %{{x}}: %{{y:,.1f}}<extra></extra>",
        )
    fig.update_layout(yaxis_title=label, margin=dict(l=56, r=12, t=28, b=28))
    return _graph(fig, height)


def stacked_area(
    years: Sequence, series: Sequence[dict], *, label: str = "", height: int = 280
) -> dcc.Graph:
    """Stacked area composition over time. series=[{name, color, ys}]."""
    fig = go.Figure()
    for i, s in enumerate(series):
        fig.add_scatter(
            x=list(years),
            y=list(s["ys"]),
            mode="lines",
            name=s["name"],
            line=dict(width=0.5, color=s.get("color", theme.VIZ_SCALE[i % len(theme.VIZ_SCALE)])),
            stackgroup="one",
            fillcolor=_rgba(s.get("color", theme.VIZ_SCALE[i % len(theme.VIZ_SCALE)]), 0.55),
            hovertemplate=f"{s['name']} · %{{x}}: %{{y:,.0f}}<extra></extra>",
        )
    fig.update_layout(yaxis_title=label, margin=dict(l=56, r=12, t=28, b=28))
    return _graph(fig, height)


def lorenz(curve_pts: Sequence[float], *, height: int = 260, label: str = "") -> dcc.Graph:
    """Lorenz curve (cumulative share) with the equality diagonal reference."""
    n = len(curve_pts)
    xs = [i / (n - 1) for i in range(n)] if n > 1 else [0, 1]
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        line=dict(color=theme.FG_4, width=1, dash="dash"),
        name="Igualdade",
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=xs,
        y=list(curve_pts),
        mode="lines",
        line=dict(color=theme.YALE_BLUE, width=2),
        fill="tonexty",
        fillcolor=_rgba(theme.YALE_BLUE, 0.10),
        name="Lorenz",
        hovertemplate="%{x:.0%} dos produtores · %{y:.0%} do total<extra></extra>",
    )
    fig.update_layout(
        yaxis_title=label or "Participação acumulada",
        margin=dict(l=56, r=12, t=12, b=36),
        showlegend=False,
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    return _graph(fig, height)


def sparkline_svg(
    values: Sequence[float], *, color: str = theme.YALE_BLUE, width: int = 120, height: int = 32
) -> html.Img:
    """Lightweight inline-SVG sparkline (data URI) for KPI cards."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return html.Img(src="", className="kpi-spark", alt="")
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    n = len(vals)
    pad = 2
    pts = " ".join(
        f"{pad + i / (n - 1) * (width - 2 * pad):.1f},"
        f"{pad + (1 - (v - lo) / span) * (height - 2 * pad):.1f}"
        for i, v in enumerate(vals)
    )
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"width='{width}' height='{height}'>"
        f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='1.6' "
        f"stroke-linecap='round' stroke-linejoin='round'/></svg>"
    )
    return html.Img(
        src="data:image/svg+xml;utf8," + quote(svg),
        className="kpi-spark",
        alt="",
        style={"width": f"{width}px", "height": f"{height}px"},
    )


def _rgba(color: str, alpha: float) -> str:
    """Hex (#rrggbb) → rgba() with alpha. Passes CSS var()s through unchanged."""
    if not color.startswith("#") or len(color) != 7:
        return color
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"
