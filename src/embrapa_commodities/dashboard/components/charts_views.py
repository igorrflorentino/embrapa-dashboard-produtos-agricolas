"""Plotly figure builders for the 4 new primary views (Task #5).

A sibling to `charts.py` — same house style, same `embrapa` template
inheritance, same empty-data fallback pattern, same pt-BR hover text.
Kept in a separate file purely to honour the 500-LOC ceiling for
dashboard modules (see `scripts/check_dashboard_size.py`); semantically
they are part of the same library.

Imports `_empty`, `_alpha`, `_HOVER_FONT` from `.charts` so the two
files share the exact same empty annotation, alpha helper, and hover
font — no drift between the two file's visual identity.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from embrapa_commodities.dashboard.components.charts import _HOVER_FONT, _alpha, _empty
from embrapa_commodities.dashboard.theme import VIZ_COLORS

# Quality-flag palette aligned with the design system (green = OK, terracotta
# = error, amber = warn, gray = muted). Used by `stacked_area_quality` and
# `heatmap_uf_year_quality` so the same flag is always the same colour.
_QUALITY_COLORS = {
    "OK": "#006f35",  # embrapa green
    "MISSING_VALUE": "#B7791F",  # amber
    "MISSING_QUANTITY": "#B23A2B",  # terracotta
    "INCOMPLETE": "#666666",  # gray
}

# Diverging green→red scale for "% OK" heatmaps. Higher = greener, lower = red.
_QUALITY_SCALE = [
    [0.0, "#B23A2B"],  # 0% OK = bad
    [0.5, "#B7791F"],  # 50% = amber
    [1.0, "#006f35"],  # 100% OK = good
]


def treemap_region_state(df: pd.DataFrame, *, value_label: str) -> go.Figure:
    """Hierarchical treemap: 5 regions → 27 UFs sized & coloured by value.

    Replaces a flat top-states bar with a single component that shows
    regional concentration at a glance — ideal for the executive-level
    Geografia view. Each region is a parent block; states nest inside.

    Input cols: ``region``, ``state_name``, ``value``.
    """
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    df = df[df["value"] > 0].copy()
    if df.empty:
        return _empty(fig)
    region_totals = (
        df.groupby("region", as_index=False)
        .agg(value=("value", "sum"))
        .assign(parent="")
        .rename(columns={"region": "labels"})
    )
    state_rows = df.assign(parent=df["region"]).rename(columns={"state_name": "labels"})[
        ["labels", "parent", "value"]
    ]
    nodes = pd.concat([region_totals[["labels", "parent", "value"]], state_rows], ignore_index=True)
    fig.add_trace(
        go.Treemap(
            labels=nodes["labels"],
            parents=nodes["parent"],
            values=nodes["value"],
            branchvalues="total",
            marker=dict(
                colors=nodes["value"],
                colorscale=[
                    [0.0, "#cddee9"],
                    [0.5, "#3A74B0"],
                    [1.0, "#1D4D7E"],
                ],
                line=dict(color="#fff", width=1),
            ),
            tiling=dict(packing="squarify", squarifyratio=1.4),
            hovertemplate=("<b>%{label}</b><br>" + value_label + ": %{value:,.0f}<extra></extra>"),
            textfont=dict(size=12, color="#fff"),
        )
    )
    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=8, b=0),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    return fig


def heatmap_region_year(df: pd.DataFrame, *, value_label: str) -> go.Figure:
    """Heatmap of regional production over time. X = year, Y = 5 regions, color = value.

    Input cols: ``reference_year``, ``region``, ``value``.
    """
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    pivot = (
        df.pivot_table(
            index="region",
            columns="reference_year",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"])
        .dropna(how="all")
    )
    fig.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[[0.0, "#FFFFFF"], [1.0, "#1D4D7E"]],
            colorbar=dict(
                title=dict(text=value_label, font=dict(size=11, color="#666")),
                thickness=10,
                len=0.7,
                outlinewidth=0,
                tickfont=dict(size=10, color="#666"),
            ),
            hovertemplate=("<b>%{y}</b> · %{x}<br>" + value_label + ": %{z:,.0f}<extra></extra>"),
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(l=80, r=16, t=16, b=40),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def heatmap_uf_year_quality(df: pd.DataFrame) -> go.Figure:
    """Heatmap of % OK by (UF × year). Diverging scale: red (low) → amber → green (high).

    Input cols: ``state_acronym``, ``reference_year``, ``pct_ok`` (0.0–1.0).
    """
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    pivot = df.pivot_table(
        index="state_acronym",
        columns="reference_year",
        values="pct_ok",
        aggfunc="mean",
    ).sort_index()
    fig.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            zmin=0.0,
            zmax=1.0,
            colorscale=_QUALITY_SCALE,
            colorbar=dict(
                title=dict(text="% OK", font=dict(size=11, color="#666")),
                thickness=10,
                len=0.7,
                outlinewidth=0,
                tickformat=".0%",
                tickfont=dict(size=10, color="#666"),
            ),
            hovertemplate=("<b>%{y}</b> · %{x}<br>% OK: %{z:.1%}<extra></extra>"),
        )
    )
    fig.update_layout(
        height=max(260, 14 * len(pivot.index) + 80),
        margin=dict(l=56, r=16, t=16, b=40),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def stacked_area_quality(df: pd.DataFrame) -> go.Figure:
    """Stacked area: count of rows by data_quality_flag over time.

    OK at the bottom (green), then MISSING_VALUE / MISSING_QUANTITY,
    INCOMPLETE on top — reads as "the green base is good data; the
    colourful slab on top is the gap to watch".

    Input cols: ``reference_year``, ``data_quality_flag``, ``count``.
    """
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    stack_order = ["OK", "MISSING_VALUE", "MISSING_QUANTITY", "INCOMPLETE"]
    for flag in stack_order:
        sub = df[df["data_quality_flag"] == flag].sort_values("reference_year")
        if sub.empty:
            continue
        color = _QUALITY_COLORS[flag]
        fig.add_trace(
            go.Scatter(
                x=sub["reference_year"],
                y=sub["count"],
                mode="lines",
                stackgroup="quality",
                name=flag,
                line=dict(width=0.6, color=color),
                fillcolor=_alpha(color, 0.85),
                hovertemplate=("<b>%{x}</b> · " + flag + "<br>%{y:,.0f} linhas<extra></extra>"),
            )
        )
    fig.update_layout(
        height=320,
        hoverlabel=dict(font=_HOVER_FONT),
        legend=dict(orientation="h", y=1.05, x=0),
    )
    fig.update_xaxes(tickformat="d", dtick=5)
    return fig


def small_multiples_commodities(
    df: pd.DataFrame,
    *,
    value_label: str,
    indexed: bool = False,
    cols: int = 3,
) -> go.Figure:
    """Grid of mini-line charts, one per commodity. Compares trajectories.

    With ``indexed=True``, each commodity is normalised to 100 at its first
    year in the window — lets the user compare growth shapes between
    commodities of very different absolute magnitudes (e.g. castanha vs
    madeira em tora).

    Input cols: ``reference_year``, ``product_description``, ``value``.
    """
    fig = go.Figure()
    if df.empty:
        return _empty(fig)
    products = sorted(df["product_description"].dropna().unique().tolist())
    if not products:
        return _empty(fig)
    n = len(products)
    cols = max(1, min(cols, n))
    rows = math.ceil(n / cols)
    subplot_titles = [str(p) for p in products]
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=subplot_titles,
        shared_xaxes=False,
        shared_yaxes=indexed,
        horizontal_spacing=0.08,
        vertical_spacing=0.18,
    )
    for i, product in enumerate(products):
        row = i // cols + 1
        col = i % cols + 1
        sub = df[df["product_description"] == product].sort_values("reference_year").copy()
        if sub.empty:
            continue
        if indexed:
            first = sub["value"].iloc[0]
            sub["plot_y"] = 100.0 * sub["value"] / first if first else 0.0
            y_label = "Índice (base 100)"
        else:
            sub["plot_y"] = sub["value"]
            y_label = value_label
        color = VIZ_COLORS[i % len(VIZ_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=sub["reference_year"],
                y=sub["plot_y"],
                mode="lines",
                line=dict(color=color, width=2),
                fill="tozeroy",
                fillcolor=_alpha(color, 0.10),
                name=str(product),
                showlegend=False,
                hovertemplate=("<b>%{x}</b><br>" + y_label + ": %{y:,.2f}<extra></extra>"),
            ),
            row=row,
            col=col,
        )
        fig.update_xaxes(tickformat="d", dtick=5, row=row, col=col)
    # Downshade subplot titles to match the caption tier.
    for annotation in fig["layout"]["annotations"]:
        annotation.update(font=dict(size=11, color="#666"))
    fig.update_layout(
        height=max(220, 200 * rows),
        margin=dict(l=48, r=16, t=32, b=32),
        hoverlabel=dict(font=_HOVER_FONT),
    )
    return fig


def municipal_choropleth(
    df: pd.DataFrame,
    geojson: dict | None,
    *,
    value_label: str,
) -> go.Figure:
    """Choropleth at municipal grain for a single UF.

    Falls back to a top-20 horizontal bar of city names when ``geojson``
    is unavailable (IBGE API hiccup). Uses ``properties.codarea`` as the
    feature key — matches IBGE's municipal mesh shape.

    Input cols: ``city_code`` (7-digit IBGE), ``city_name``, ``value``.
    """
    if df.empty:
        return _empty(go.Figure())
    if geojson is None:
        df_sorted = df.sort_values("value", ascending=False).head(20).sort_values("value")
        fig = go.Figure(
            go.Bar(
                x=df_sorted["value"],
                y=df_sorted["city_name"],
                orientation="h",
                marker=dict(color=VIZ_COLORS[0], line=dict(width=0)),
                hovertemplate=("<b>%{y}</b><br>" + value_label + ": %{x:,.0f}<extra></extra>"),
            )
        )
        fig.update_layout(
            height=max(220, 22 * len(df_sorted) + 60),
            showlegend=False,
            margin=dict(l=180, r=24, t=16, b=32),
            hoverlabel=dict(font=_HOVER_FONT),
        )
        fig.update_xaxes(title=value_label)
        return fig
    locations = df["city_code"].astype(str)
    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            locations=locations,
            featureidkey="properties.codarea",
            z=df["value"],
            colorscale=[
                [0.0, "#cddee9"],
                [0.5, "#3A74B0"],
                [1.0, "#1D4D7E"],
            ],
            marker=dict(line=dict(color="#fff", width=0.3)),
            colorbar=dict(
                title=dict(text=value_label, font=dict(size=11, color="#666")),
                thickness=10,
                len=0.7,
                outlinewidth=0,
                tickfont=dict(size=10, color="#666"),
            ),
            hovertemplate=(
                "<b>"
                + (df["city_name"].astype(str) + " (%{location})")
                + "</b><br>"
                + value_label
                + ": %{z:,.0f}<extra></extra>"
            ),
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


__all__ = [
    "heatmap_region_year",
    "heatmap_uf_year_quality",
    "municipal_choropleth",
    "small_multiples_commodities",
    "stacked_area_quality",
    "treemap_region_state",
]
