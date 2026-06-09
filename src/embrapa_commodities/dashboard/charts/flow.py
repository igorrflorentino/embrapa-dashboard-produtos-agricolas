"""Trade-flow Plotly charts: Sankey, month×year heatmap, monthly-average bars."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc

from .. import theme
from ..format import MONTH_ABBR_PT

_CONFIG = {"displayModeBar": False, "responsive": True}


def sankey(
    links,
    origin_label: str = "Origem",
    dest_label: str = "Destino",
    *,
    top: int = 25,
    height: int = 380,
) -> dcc.Graph:
    """Origin→destination Sankey from a links DataFrame (top-N links by value).

    Origins coloured Yale blue, destinations green; links a translucent blue —
    the data palette, never chrome green dominating.
    """
    df = links.sort_values("value_usd", ascending=False).head(top)
    origins = list(dict.fromkeys(df["origin_code"]))
    dests = list(dict.fromkeys(df["dest_code"]))
    o_name = dict(zip(df["origin_code"], df["origin_name"], strict=False))
    d_name = dict(zip(df["dest_code"], df["dest_name"], strict=False))
    labels: list[str] = []
    colors: list[str] = []
    idx: dict = {}
    for o in origins:
        idx[("o", o)] = len(labels)
        labels.append(str(o_name.get(o, o)))
        colors.append(theme.YALE_BLUE)
    for d in dests:
        idx[("d", d)] = len(labels)
        labels.append(str(d_name.get(d, d)))
        colors.append(theme.EMBRAPA_GREEN)
    src = [idx[("o", r.origin_code)] for r in df.itertuples()]
    tgt = [idx[("d", r.dest_code)] for r in df.itertuples()]
    fig = go.Figure(
        go.Sankey(
            node=dict(
                label=labels, color=colors, pad=14, thickness=12, line=dict(color="#fff", width=0.5)
            ),
            link=dict(
                source=src, target=tgt, value=df["value_usd"].tolist(), color="rgba(29,77,126,0.20)"
            ),
        )
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(size=12, color=theme.FG_2),
    )
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")


def month_year_heatmap(monthly, *, height: int | None = None) -> dcc.Graph:
    """month×year heatmap of monthly value on the institutional heat ramp."""
    years = sorted(int(y) for y in monthly["reference_year"].unique())
    z = []
    for y in years:
        row = [0.0] * 12
        sub = monthly[monthly["reference_year"] == y]
        for r in sub.itertuples():
            m = int(r.reference_month)
            if 1 <= m <= 12:
                row[m - 1] = float(r.total_value_usd or 0)
        z.append(row)
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=MONTH_ABBR_PT,
            y=[str(y) for y in years],
            colorscale=theme.heat_colorscale(),
            colorbar=dict(title=dict(text="US$", side="right"), thickness=10, outlinewidth=0),
            hovertemplate="%{x}/%{y}: US$ %{z:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height or (26 * len(years) + 90),
        margin=dict(l=48, r=12, t=12, b=28),
    )
    fig.update_yaxes(autorange="reversed")
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")


def monthly_bars(avg12, *, height: int = 300) -> dcc.Graph:
    """12-month average bars (perfil sazonal médio), amber per the design."""
    fig = go.Figure(
        go.Bar(
            x=MONTH_ABBR_PT,
            y=list(avg12),
            marker=dict(color=theme.WARN),
            hovertemplate="%{x}: US$ %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        height=height,
        showlegend=False,
        margin=dict(l=56, r=12, t=12, b=28),
    )
    return dcc.Graph(figure=fig, config=_CONFIG, className="chart")
