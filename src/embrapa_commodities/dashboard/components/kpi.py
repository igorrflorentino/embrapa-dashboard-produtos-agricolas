"""KPI cards — plain and with sparkline."""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go
from dash import dcc, html

from embrapa_commodities.dashboard.components.icons import icon


def _sparkline_figure(values: Sequence[float], color: str) -> go.Figure:
    """Tiny line chart for KPI cards. No axes, no margins, no hover."""
    xs = list(range(len(values)))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=list(values),
            mode="lines",
            line=dict(color=color, width=1.6),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.10),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    if values:
        fig.add_trace(
            go.Scatter(
                x=[xs[-1]],
                y=[values[-1]],
                mode="markers",
                marker=dict(size=4, color=color),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=32,
        width=120,
        xaxis=dict(visible=False, showgrid=False, fixedrange=True),
        yaxis=dict(visible=False, showgrid=False, fixedrange=True, rangemode="tozero"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _rgba(color: str, alpha: float) -> str:
    """Translate a hex color (with #) to rgba() with the given alpha."""
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return color  # already rgba() or var(--*) — fall through


def _kpi_top_row(
    label: str,
    *,
    has_spark: bool,
    spark_values: Sequence[float] | None,
    spark_color: str,
) -> html.Div:
    """Top row: label + optional sparkline. ``has_spark`` is resolved by the
    caller so the className decision in ``kpi_card`` stays consistent with
    the actual rendered children."""
    children: list = [html.Div(label, className="kpi-ov")]
    if has_spark:
        children.append(
            dcc.Graph(
                figure=_sparkline_figure(list(spark_values or []), spark_color),
                config={"displayModeBar": False, "staticPlot": True},
                className="kpi-spark",
            )
        )
    return html.Div(children, className="kpi-top")


def _kpi_sub_row(
    delta: str | None,
    delta_positive: bool | None,
    sub: str | None,
) -> html.Div | None:
    """Sub row: optional delta-arrow + optional caption. Returns None when
    neither component is present so the caller can skip appending it."""
    if delta is None and sub is None:
        return None
    children: list = []
    if delta is not None:
        arrow = "arrow_upward" if delta_positive else "arrow_downward"
        children.append(
            html.Span(
                children=[icon(arrow, size=12), html.Span(delta)],
                className=f"kpi-delta {'up' if delta_positive else 'down'}",
            )
        )
    if sub is not None:
        children.append(html.Span(sub))
    return html.Div(children, className="kpi-sub")


def kpi_card(
    *,
    label: str,
    value: str,
    sub: str | None = None,
    delta: str | None = None,
    delta_positive: bool | None = None,
    spark_values: Sequence[float] | None = None,
    spark_color: str = "#1D4D7E",
) -> html.Div:
    """Render a KPI card. Spark is optional; if provided, the card uses the `spark` variant."""
    has_spark = spark_values is not None and len(list(spark_values)) > 1
    children: list = [
        _kpi_top_row(
            label, has_spark=has_spark, spark_values=spark_values, spark_color=spark_color
        ),
        html.Div(value, className="kpi-val tnum"),
    ]
    sub_row = _kpi_sub_row(delta, delta_positive, sub)
    if sub_row is not None:
        children.append(sub_row)
    return html.Div(
        children=children,
        className="kpi-card spark" if has_spark else "kpi-card",
    )
