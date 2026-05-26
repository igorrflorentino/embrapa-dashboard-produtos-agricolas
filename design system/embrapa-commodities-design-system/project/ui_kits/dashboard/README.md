# Dashboard — UI kit

A pixel-fidelity recreation of the **Dashboard de Inteligência de Mercado de Commodities** as it would appear in Looker Studio (or its successor surface).

> **Note:** The upstream repo `igorrflorentino/embrapa-dashboard-commodities` is a Python + dbt + BigQuery data pipeline; the actual report lives in Looker Studio and the team has not published screenshots. This UI kit is built **from the data schema** (`gold_commodity_matrix`) and Embrapa's brand foundations — not from an existing screenshot. Treat it as a directional reference; confirm with the dashboard owner before treating any specific chart as canonical.

## Screens

| Route | Component | What it shows |
|---|---|---|
| `overview` | `Overview.jsx` | KPIs (valor real IPCA, quantidade, cobertura, qualidade) + time series + product mix + top UFs + table sample |
| `product` | `Screens.jsx → ProductScreen` | Single-product drill-down |
| `geo` | `Screens.jsx → GeoScreen` | UF ranking + map placeholder |
| `quality` | `Screens.jsx → QualityScreen` | data_quality_flag distribution |

## Component map

```
AppShell.jsx           Topbar (Embrapa green) + sidebar + footer with tríade
FilterBar.jsx          Period, product, UF, monetary convention, currency, OK-only toggle
Atoms.jsx              KpiCard, SectionHeader, StatusChip
Charts.jsx             LineChart, BarChart, Donut — all hand-rolled SVG, no library
DataTable.jsx          gold_commodity_matrix sample rows
Overview.jsx           Composes the main dashboard view
Screens.jsx            Secondary routes
data.js                Mock data shaped like the Gold table
dashboard.css          Layout-specific styles (extends colors_and_type.css)
```

## Open

`ui_kits/dashboard/index.html`

## Conventions honored

- **Header band is `--embrapa-green`** — institutional brand band, never the data palette.
- **Charts use the presentations palette** (Yale Blue, French Blue, etc.) — keeps data readable on white.
- **Numbers are tabular** (`font-variant-numeric: tabular-nums`) so columns of figures line up.
- **Monetary convention is exposed** in the filter bar — IPCA / IGP-M / FX of year, plus currency. This is non-negotiable on this dataset; the README states explicitly that cross-year comparisons require IPCA chain.
- **Empregados** tag at the bottom of the sidebar — the brand orange `#cc4b10` reserved for restricted-access labeling per the Mobile guide.
- **Triade footer** — Embrapa + Ministério + Gov.BR lockup, as institutional rules require.
