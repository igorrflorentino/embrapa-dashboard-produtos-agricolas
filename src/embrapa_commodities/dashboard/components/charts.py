"""Plotly figure builders themed by the embrapa template.

Each function returns a `go.Figure` ready for embedding in `dcc.Graph`. None
of them mutate the input DataFrame.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from embrapa_commodities.dashboard.theme import VIZ_COLORS

_HOVER_FONT = dict(family="Univers, Arial, sans-serif", size=12, color="#1a1f1c")


def line_time_series(df: pd.DataFrame, *, value_label: str, value_col: str = "value") -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    fig.add_trace(
        go.Scatter(
            x=df["reference_year"],
            y=df[value_col],
            mode="lines+markers",
            line=dict(color=VIZ_COLORS[0], width=2),
            marker=dict(size=4, color=VIZ_COLORS[0]),
            fill="tozeroy",
            fillcolor=_alpha(VIZ_COLORS[0], 0.10),
            hovertemplate=("<b>%{x}</b><br>" + value_label + ": %{y:,.2f}<extra></extra>"),
            name=value_label,
        )
    )
    fig.update_layout(height=280, hoverlabel=dict(font=_HOVER_FONT))
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def bar_top_states(df: pd.DataFrame, *, value_label: str) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    # Horizontal bar; biggest on top.
    df_sorted = df.sort_values("value")
    fig.add_trace(
        go.Bar(
            x=df_sorted["value"],
            y=df_sorted["state_name"],
            orientation="h",
            marker=dict(color=VIZ_COLORS[1], line=dict(width=0)),
            hovertemplate=("<b>%{y}</b><br>" + value_label + ": %{x:,.0f}<extra></extra>"),
        )
    )
    fig.update_layout(
        height=max(220, 28 * len(df) + 60),
        showlegend=False,
        margin=dict(l=120, r=24, t=16, b=32),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    fig.update_xaxes(title=value_label)
    return fig


def donut_product_mix(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    colors = VIZ_COLORS[: len(df)]
    # Pull "Outros" out of the brand palette into gray so it doesn't compete.
    if "_other" in df["product_code"].values:
        idx = df.index[df["product_code"] == "_other"][0]
        colors = list(colors)
        if idx < len(colors):
            colors[idx] = "#ECECEC"
    # Hide labels for slices under 3% — they round to 0% / clutter the ring.
    total = float(df["value"].sum()) or 1.0
    text_values = [f"{(v / total * 100):.0f}%" if (v / total) >= 0.03 else "" for v in df["value"]]
    fig.add_trace(
        go.Pie(
            labels=df["product_description"],
            values=df["value"],
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker=dict(colors=colors, line=dict(color="#fff", width=2)),
            text=text_values,
            textinfo="text",
            textfont=dict(size=11, color="#1a1f1c"),
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        height=300,
        margin=dict(l=8, r=8, t=8, b=8),
        legend=dict(
            orientation="v",
            x=1.02,
            y=0.5,
            yanchor="middle",
            font=dict(size=11, color="#666"),
        ),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    return fig


def line_with_secondary(
    df: pd.DataFrame,
    *,
    value_label: str,
    quantity_label: str,
) -> go.Figure:
    """Two-line chart: primary value (left axis) + quantity (right axis)."""
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    fig.add_trace(
        go.Scatter(
            x=df["reference_year"],
            y=df["value"],
            mode="lines+markers",
            name=value_label,
            line=dict(color=VIZ_COLORS[0], width=2),
            marker=dict(size=4),
            hovertemplate=("<b>%{x}</b><br>" + value_label + ": %{y:,.0f}<extra></extra>"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["reference_year"],
            y=df["quantity"],
            mode="lines+markers",
            name=quantity_label,
            line=dict(color=VIZ_COLORS[1], width=2, dash="dot"),
            marker=dict(size=4),
            yaxis="y2",
            hovertemplate=("<b>%{x}</b><br>" + quantity_label + ": %{y:,.0f}<extra></extra>"),
        )
    )
    fig.update_layout(
        height=320,
        yaxis=dict(title=value_label),
        yaxis2=dict(
            title=quantity_label,
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        hoverlabel=dict(font=_HOVER_FONT),
        legend=dict(orientation="h", y=1.08, x=0),
    )
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def choropleth_brazil(
    df: pd.DataFrame,
    geojson: dict | None,
    *,
    value_label: str,
) -> go.Figure:
    """Choropleth of UFs colored by total value.

    Falls back to a horizontal bar chart if `geojson` is None or fetch failed.
    """
    if df.empty or geojson is None:
        return bar_top_states(df, value_label=value_label)
    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            locations=df["state_acronym"],
            featureidkey="properties.sigla",
            z=df["value"],
            colorscale=[
                [0.0, "#cddee9"],
                [0.5, "#3A74B0"],
                [1.0, "#1D4D7E"],
            ],
            marker=dict(line=dict(color="#fff", width=0.5)),
            colorbar=dict(
                title=dict(text=value_label, font=dict(size=11, color="#666")),
                thickness=10,
                len=0.7,
                outlinewidth=0,
                tickfont=dict(size=10, color="#666"),
            ),
            hovertemplate=("<b>%{location}</b><br>" + value_label + ": %{z:,.0f}<extra></extra>"),
        )
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    return fig


def stacked_product_area(df: pd.DataFrame, *, value_label: str) -> go.Figure:
    """Stacked area: x = year, traces = top products, y = value."""
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    products = df["product_description"].unique().tolist()
    for i, product in enumerate(products):
        sub = df[df["product_description"] == product].sort_values("reference_year")
        fig.add_trace(
            go.Scatter(
                x=sub["reference_year"],
                y=sub["value"],
                mode="lines",
                stackgroup="one",
                name=product,
                line=dict(width=0.6, color=VIZ_COLORS[i % len(VIZ_COLORS)]),
                fillcolor=_alpha(VIZ_COLORS[i % len(VIZ_COLORS)], 0.85),
                hovertemplate=(
                    "<b>%{x}</b> · " + product + "<br>" + value_label + ": %{y:,.0f}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        height=320,
        hoverlabel=dict(font=_HOVER_FONT),
        legend=dict(orientation="h", y=1.05, x=0),
    )
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def _empty(fig: go.Figure) -> go.Figure:
    fig.add_annotation(
        text="Sem dados para os filtros selecionados.",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color="#9aa5a0"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=240)
    return fig


def _alpha(color: str, alpha: float) -> str:
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return color
