---
name: new-chart-component
description: >-
  Create a new chart type, Plotly figure builder, KPI card variant, or visual
  component for the dashboard. Use when asked to add a new visualization,
  create a new chart type, modify chart styling, or build a new reusable
  dashboard component.
---

# New Chart / Component — Embrapa Dashboard

## Chart Builder Pattern (`components/charts.py`)

Every chart is a **pure function**: `(DataFrame, **kwargs) → go.Figure`. No side effects, no mutations.

```python
def my_chart(df: pd.DataFrame, *, value_label: str) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return _empty(fig)  # standard "Sem dados" fallback

    fig.add_trace(
        go.Scatter(  # or go.Bar, go.Pie, etc.
            x=df["reference_year"],
            y=df["value"],
            # ... trace config ...
            hovertemplate=(
                "<b>%{x}</b><br>" + value_label + ": %{y:,.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=280,
        hoverlabel=dict(font=_HOVER_FONT),
    )
    return fig
```

## Design System Constants (`theme.py`)

```python
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
```

**Never hardcode colors or fonts.** Use `VIZ_COLORS[i]` and reference `FONT_FAMILY`.

## Template (`EMBRAPA_TEMPLATE`)

`install_template()` is called once at startup. All `go.Figure` objects auto-inherit:
- White background, clean grid
- Univers font family
- Separators: `,` for thousands, `.` for decimal (Brazilian convention)
- Bottom legend, horizontal orientation
- Hover label with white bg and border

You do NOT need to set these on individual figures.

## Helper Utilities

### `_empty(fig)` — Empty data fallback
Returns a figure with a centered "Sem dados para os filtros selecionados." annotation. **Always use this** when `df.empty`.

### `_alpha(color, alpha)` — Transparency
Converts `#RRGGBB` to `rgba(r,g,b,alpha)`. Used for fill areas:
```python
fillcolor=_alpha(VIZ_COLORS[0], 0.10)
```

### `_HOVER_FONT`
Standard hover tooltip font:
```python
_HOVER_FONT = dict(family="Univers, Arial, sans-serif", size=12, color="#1a1f1c")
```

## Existing Chart Types (in `charts.py`)

| Function | Trace type | Usage |
|----------|------------|-------|
| `line_time_series` | `go.Scatter` (lines+markers+fill) | Time series with area fill |
| `bar_top_states` | `go.Bar` (horizontal) | Ranking by state |
| `donut_product_mix` | `go.Pie` (hole=0.62) | Product share donut |
| `line_with_secondary` | 2× `go.Scatter` (dual y-axis) | Value + quantity overlay |
| `choropleth_brazil` | `go.Choropleth` | Brazil UF map (fallback to bar) |
| `stacked_product_area` | `go.Scatter` (stackgroup) | Multi-product area chart |

## Existing Non-Chart Components

| Component | File | API |
|-----------|------|-----|
| `kpi_card(label, value, delta, spark_values, ...)` | `components/kpi.py` | KPI card with inline sparkline |
| `filter_bar(prefix, store)` | `components/filter_bar.py` | Period/product/UF/convention/currency filters |
| `section_header(overline, title, action=)` | `components/section_header.py` | Section heading with optional action slot |
| `monetary_legend()` | `components/monetary_legend.py` | Monetary convention explanation card |
| `export_button() + download_payload()` | `components/export.py` | CSV download button + dcc.Download |
| `shell(content, path, source, view)` | `components/shell.py` | Page shell with sidebar + top nav |

## CSS Classes (from `assets/`)

Layout: `screen`, `card`, `grid-2`, `kpi-row`, `highlights`, `highlights-grid`
Typography: `page-hero`, `page-title`, `page-sub`, `overline`, `section-title`, `caption`, `tnum`
Badges: `chip`, `chip ok`, `chip err`, `chip info`
Metadata: `meta-row`, `meta-label`, `meta-val`
Empty: `empty-state`
Loading: `loading-wrap`

## Adding a New Chart — Checklist

1. Add the function to `components/charts.py`.
2. Follow the pattern: `(df, **kwargs) → go.Figure`, handle empty with `_empty(fig)`.
3. Use `VIZ_COLORS` for palette, `_HOVER_FONT` for tooltips.
4. Set explicit `height` in `update_layout()` (the template doesn't set height).
5. Import and use in the relevant page module.
6. Test with empty DataFrame input to ensure graceful fallback.

## Adding a New Non-Chart Component — Checklist

1. Create file in `components/<name>.py`.
2. Export a function that returns `html.Div` (or another Dash component).
3. If it has callbacks, register them in the page's `register_callbacks`, NOT in the component itself.
4. Use `{"section": PREFIX, "control": "<name>"}` pattern-matching IDs.
5. Add to `components/__init__.py` if it should be easily importable.
