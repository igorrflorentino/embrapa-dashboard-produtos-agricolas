---
name: dash-page-scaffold
description: >-
  Create a new page, view, or section in the Dash dashboard. Use when asked to
  add a new view, create a new dashboard page, add a new tab or section to the
  web app, or scaffold a new analytical perspective in the dashboard.
---

# Dash Page Scaffold — Embrapa Dashboard

## Architecture

The dashboard is **source-scoped**. Each `DataSource` declares its views and store. URLs are `/<source-id>/<view-id>`.

```
DataSource (ibge-pevs)
├── primary_views:   visão-geral, produto, geografia  (top nav)
├── sidebar_sections:
│   ├── Dados:   tabela, export, sobre-api
│   └── Sobre:   glossário, dados
└── store:           GoldStore (in-memory BigQuery snapshot)
```

The only global page is `/status`.

## Creating a New Page — Step by Step

### 1. Create the page module

File: `src/embrapa_commodities/dashboard/pages/<page_name>.py`

```python
"""<View slug> — <Short description>.

<What the page shows and why.>
"""

from __future__ import annotations

from dash import Input, Output, State, dcc, html, no_update

from embrapa_commodities.dashboard.components.charts import <chart_functions>
from embrapa_commodities.dashboard.components.filter_bar import filter_bar
from embrapa_commodities.dashboard.components.kpi import kpi_card
from embrapa_commodities.dashboard.components.monetary_legend import monetary_legend
from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore
from embrapa_commodities.dashboard.formatting import convention_label, fmt_currency, fmt_number

# CRITICAL: PREFIX must be globally unique across ALL pages.
# It is used as the "section" key in pattern-matching callback IDs.
PREFIX = "<unique_page_prefix>"


def layout(store: GoldStore) -> html.Div:
    """Render the page layout. Called on route match."""
    return html.Div(
        className="screen",
        children=[
            # hero, filter_bar, KPI strip, charts, etc.
            filter_bar(PREFIX, store),
            # ... charts and sections ...
            monetary_legend(),
        ],
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    """Register all callbacks. Called ONCE at app startup (eagerly)."""
    from embrapa_commodities.dashboard.app import build_error_payload

    @dash_app.callback(
        Output({"section": PREFIX, "control": "<output>"}, "children"),
        Output("global-error", "data", allow_duplicate=True),
        Input({"section": PREFIX, "control": "period"}, "value"),
        Input({"section": PREFIX, "control": "product"}, "value"),
        Input({"section": PREFIX, "control": "uf"}, "value"),
        Input({"section": PREFIX, "control": "conv"}, "value"),
        Input({"section": PREFIX, "control": "ccy"}, "value"),
        Input({"section": PREFIX, "control": "only_ok"}, "value"),
        prevent_initial_call="initial_duplicate",
    )
    def _update(period, product, uf, conv, ccy, only_ok):
        try:
            # ... build charts, KPIs ...
            return result, no_update
        except Exception as exc:
            err = build_error_payload(
                exc, page="/<source>/<view>", where="callback de atualização (<page>)"
            )
            return no_update, err


__all__ = ["PREFIX", "layout", "register_callbacks"]
```

### 2. Register the view in `data_sources.py`

Add the import and `View(...)` entry in `build_registry()`:

```python
from embrapa_commodities.dashboard.pages import new_page

# In the DataSource's primary_views or sidebar_sections:
View(
    id="<url-slug>",           # e.g. "minha-view"
    label="<Display Label>",   # e.g. "Minha View"
    icon="<material-symbol>",  # e.g. "analytics"
    layout_fn=new_page.layout,
    register_fn=new_page.register_callbacks,
),
```

### 3. Verify

```powershell
uv run --extra dashboard python scripts/dashboard_smoke.py
```

## Critical Rules

1. **Callbacks are registered EAGERLY at startup** — never inside the route callback.
   Prior versions did lazy registration, but by then `/_dash-dependencies` was already served and the client didn't know to dispatch them.

2. **PREFIX must be globally unique.** Dash uses `Output` IDs to dispatch — two callbacks with the same Output ID will clash. Current prefixes:
   `overview`, `product`, `geography`, `tabela`, `export`, `sobre_api`, `glossario`, `dados`, `status`

3. **Error handling:** Wrap the callback body in try/except and write to `global-error` store on failure:
   ```python
   except Exception as exc:
       err = build_error_payload(exc, page=path, where="description")
       return no_update, ..., err
   ```

4. **Pattern-matching IDs:** Use `{"section": PREFIX, "control": "<name>"}` for all component IDs.

## Available Components

| Component | Import | Usage |
|-----------|--------|-------|
| `filter_bar(prefix, store)` | `components.filter_bar` | Standard filter bar (period, product, UF, convention, currency) |
| `kpi_card(...)` | `components.kpi` | KPI card with sparkline |
| `section_header(overline, title)` | `components.section_header` | Section heading |
| `monetary_legend()` | `components.monetary_legend` | Explanation card for monetary conventions |
| `export_button() + download_payload()` | `components.export` | CSV/Excel download |
| `shell(content, path, source, view)` | `components.shell` | Outer shell (sidebar + topnav) — used only by `app.py` |

## Available Chart Builders (`components.charts`)

| Function | Input | Output |
|----------|-------|--------|
| `line_time_series(df, value_label=)` | `reference_year, value` | Line + area |
| `bar_top_states(df, value_label=)` | `state_name, value` | Horizontal bar |
| `donut_product_mix(df)` | `product_description, value` | Donut ring |
| `line_with_secondary(df, value_label=, quantity_label=)` | `reference_year, value, quantity` | Dual-axis line |
| `choropleth_brazil(df, geojson, value_label=)` | `state_acronym, value` | Map or bar fallback |
| `stacked_product_area(df, value_label=)` | `reference_year, product_description, value` | Stacked area |

All chart functions return `go.Figure`. They handle empty DataFrames gracefully with an "Sem dados" annotation.

## Design Tokens (from `theme.py`)

- **Colors:** Use `VIZ_COLORS` list (8 colors). Never hardcode hex in pages.
- **Font:** `FONT_FAMILY = "Univers, 'Embrapa Verdana', ..."` — set globally via template.
- **Template:** `install_template()` is called once at startup. All figures auto-inherit.
- **CSS classes:** `screen`, `card`, `grid-2`, `kpi-row`, `highlights`, `page-hero`, `overline`, `section-title`, `page-title`, `caption`, `tnum`, `chip`, `meta-row`, `empty-state`.

## GoldStore Slicers

Pages access data via the `GoldStore` instance:

| Method | Returns |
|--------|---------|
| `store.time_series(convention=, currency=, years=, ...)` | `reference_year, value, quantity` |
| `store.top_states(year=, convention=, currency=, ...)` | `state_acronym, state_name, value` |
| `store.product_mix(year=, convention=, currency=, ...)` | `product_code, product_description, value, share` |
| `store.top_cities(year=, convention=, currency=, ...)` | `city_name, state_acronym, value, quantity` |
| `store.filtered(years=, product_code=, state_acronym=, only_ok=)` | Full filtered DataFrame |
| `store.products()` | `product_code, product_description` |
| `store.states()` | `state_acronym, state_name, region` |
| `store.quality_summary()` | `pct_ok, rows_total, rows_ok, ...` |
| `store.coverage_summary(year=)` | `states, cities, products` |
