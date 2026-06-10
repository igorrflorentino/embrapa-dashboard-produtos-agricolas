"""seam output → contracts.js JSON shapes.

Pure functions (no I/O, no Flask) so they unit-test in isolation. Each turns a
``seam`` result (pandas DataFrames for the snapshot; plain dicts for the cross
producers) into the exact shape the reused React views consume — see
``PLANS/react_migration_contract_map.md`` §2 for the field-by-field mapping and
the magnitude rules (productTS.v in millions, overviewTS.v in billions, mass
quantity in mil t, volume in mi m³).

What is NOT done here (by design — these are client-side registries the views
already own, joining them server-side would duplicate + drift): UF tile coords
``col``/``row``, quality-flag ``label``/``color``, ``bancoMeta``/``metricMeta``.
The JS data layer decorates the rows we emit (keyed by ``uf`` / flag ``id``).
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Gold/PEVS physical-unit family is pt-BR ('massa'); the views key on the
# English 'mass' (dataFilters.js: `pt.family === 'mass'`). Map at the boundary.
_FAMILY_JS = {"massa": "mass", "volume": "volume"}


def _fam(value: Any) -> str:
    return _FAMILY_JS.get(value, value if isinstance(value, str) else "")


def _num(value: Any) -> float:
    """Coerce to a JSON-safe float (NaN/None → 0.0)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(f) else f


def _empty(df: pd.DataFrame | None) -> bool:
    return df is None or getattr(df, "empty", True)


# ── snapshot ──────────────────────────────────────────────────────────────────


def serialize_snapshot(snap: dict) -> dict:
    """seam.snapshot() (DataFrames) → BancoSnapshot (contracts.js:45)."""
    return {
        "products": _products(snap.get("products")),
        "productTS": _product_ts(snap.get("product_ts")),
        "overviewTS": _overview_ts(snap.get("overview_ts")),
        "ufData": _uf_data(snap.get("uf_data")),
        "quality": _quality(snap.get("quality")),
        "valueLabel": snap.get("value_label", ""),
        "preview": False,
        "_synthetic": False,
    }


def _products(df: pd.DataFrame | None) -> list[dict]:
    if _empty(df):
        return []
    return [
        {
            "code": str(r.code),
            # a few COMEX codes have no description → fall back to the code
            "name": r.name if (isinstance(r.name, str) and r.name) else str(r.code),
            "unit": r.unit,
            "family": _fam(r.family),
        }
        for r in df.itertuples()
    ]


def _product_ts(df: pd.DataFrame | None) -> dict:
    """GROUP BY code → {code: [{y, v(mi), q(mil t | mi m³), family}]}."""
    if _empty(df):
        return {}
    out: dict[str, list[dict]] = {}
    for r in df.itertuples():
        q_scale = 1e3 if r.family == "massa" else 1e6  # t→mil t, m³→mi m³
        out.setdefault(str(r.code), []).append(
            {
                "y": int(r.reference_year),
                "v": _num(r.total_value) / 1e6,
                "q": _num(r.total_qty_native) / q_scale,
                "family": _fam(r.family),
            }
        )
    return out


def _overview_ts(df: pd.DataFrame | None) -> list[dict]:
    if _empty(df):
        return []
    out = []
    for r in df.itertuples():
        q_mass = _num(getattr(r, "q_mass", 0)) / 1e3
        q_vol = _num(getattr(r, "q_vol", 0)) / 1e6
        out.append(
            {
                "y": int(r.reference_year),
                "v": _num(r.total_value) / 1e9,
                "q": q_mass,
                "q_mass": q_mass,
                "q_vol": q_vol,
            }
        )
    return out


def _uf_data(df: pd.DataFrame | None) -> list[dict]:
    # Per-UF quantity is a known gap: production_by_uf returns only total_value
    # (can't sum qty across families). value (the choropleth measure) is real;
    # q_mass/q_vol = 0 until a family-aware per-UF reader exists. col/row added
    # client-side from UF_DATA.
    if _empty(df):
        return []
    return [
        {
            "uf": r.state_acronym,
            "name": r.state_name,
            "region": r.region_abbrev,
            "value": _num(r.total_value) / 1e6,
            "q_mass": 0.0,
            "q_vol": 0.0,
        }
        for r in df.itertuples()
    ]


def _quality(df: pd.DataFrame | None) -> list[dict]:
    # label/color added client-side from QUALITY_FLAGS. `share` is the mart's
    # 0-1 fraction (fmtPct ×100 expects that).
    if _empty(df):
        return []
    return [
        {"id": r.data_quality_flag, "count": int(_num(r.n_rows)), "share": _num(r.share)}
        for r in df.itertuples()
    ]


# ── cross producers (already near-shape — snake→camel + preview flag) ──────────


def serialize_cross_series(d: dict | None) -> dict | None:
    """seam.cross_series() → SeriesResult. points[].v already in display
    magnitude (do not rescale). bancoMeta/metricMeta joined client-side."""
    if d is None:
        return None
    return {**d, "preview": False}


def serialize_market_share(d: dict) -> dict:
    return {
        "preview": False,
        "unit": d.get("unit", ""),
        "series": d.get("series", []),
        "byProduct": d.get("by_product", []),
    }


def serialize_export_coef(d: dict) -> dict:
    out = {
        "preview": False,
        "unit": d.get("unit", ""),
        "byUf": d.get("by_uf", []),
        "national": d.get("national", {}),
        "timeseries": d.get("timeseries", []),
    }
    if d.get("incompatible"):
        out["incompatible"] = True
    return out


def serialize_price_spread(d: dict) -> dict:
    out = {"preview": False, "unit": d.get("unit", ""), "series": d.get("series", [])}
    if d.get("incompatible"):
        out["incompatible"] = True
    return out


def serialize_trade_mirror(d: dict) -> dict:
    return {
        "preview": False,
        "unit": d.get("unit", ""),
        "series": d.get("series", []),
        "discrepancy": d.get("discrepancy", []),
    }


# ── trade adapters (flow / partner / monthly) — USD-valued, values → millions ──


def serialize_flow(d: dict | None, max_links: int = 40) -> dict:
    """seam.flow_data() → FlowData. Builds the Sankey nodes/links from the
    origin→dest link frame (top ``max_links`` by value for a readable diagram)."""
    shell = {"preview": False, "unit": "US$", "originLabel": "Origem", "destLabel": "Destino"}
    if d is None:
        return {**shell, "nodes": [], "links": []}
    links_df = d.get("links")
    origin_label = d.get("origin_label", "Origem")
    dest_label = d.get("dest_label", "Destino")
    labels = {"originLabel": origin_label, "destLabel": dest_label}
    if _empty(links_df):
        return {**shell, **labels, "nodes": [], "links": []}
    df = links_df.head(max_links)
    origins: dict[str, str] = {}
    dests: dict[str, str] = {}
    nodes: list[dict] = []
    links: list[dict] = []
    for r in df.itertuples():
        oc, dc = str(r.origin_code), str(r.dest_code)
        if oc not in origins:
            origins[oc] = f"o{len(origins)}"
            nodes.append({"id": origins[oc], "label": r.origin_name, "side": "origin", "value": 0})
        if dc not in dests:
            dests[dc] = f"d{len(dests)}"
            nodes.append({"id": dests[dc], "label": r.dest_name, "side": "dest", "value": 0.0})
        v = _num(r.value_usd) / 1e6  # → US$ mi
        links.append({"source": origins[oc], "target": dests[dc], "value": v})
    by_id = {n["id"]: n for n in nodes}
    for link in links:
        by_id[link["source"]]["value"] += link["value"]
        by_id[link["target"]]["value"] += link["value"]
    return {
        "preview": False,
        "unit": "US$",
        "originLabel": origin_label,
        "destLabel": dest_label,
        "nodes": nodes,
        "links": links,
    }


def serialize_partner(df: pd.DataFrame | None, max_rows: int = 30) -> dict:
    """seam.partner_data() → PartnerData. Partner ranking with exp/imp split (mi)."""
    if _empty(df):
        return {"preview": False, "flowLabel": "Parceiro", "unit": "US$", "partners": []}
    partners = [
        {
            "name": r.partner_name,
            "exp": _num(r.exp_value_usd) / 1e6,
            "imp": _num(r.imp_value_usd) / 1e6,
            "value": _num(r.value_usd) / 1e6,
        }
        for r in df.head(max_rows).itertuples()
    ]
    return {"preview": False, "flowLabel": "Parceiro", "unit": "US$", "partners": partners}


def serialize_monthly(df: pd.DataFrame | None) -> dict:
    """seam.monthly_data() → MonthlyData. year→12 monthly values + the 12-month avg."""
    base = {"preview": False, "unit": "US$", "months": list(range(1, 13))}
    if _empty(df):
        return {**base, "years": [], "matrix": {}, "monthlyAvg": [], "series": []}
    matrix: dict[int, list[float]] = {}
    series: list[dict] = []
    for r in df.itertuples():
        y, m = int(r.reference_year), int(r.reference_month)
        v = _num(r.total_value_usd) / 1e6
        matrix.setdefault(y, [0.0] * 12)[m - 1] = v
        series.append({"ym": f"{y}-{m:02d}", "y": y, "m": m, "v": v})
    years = sorted(matrix)
    monthly_avg = []
    for mi in range(12):
        vals = [matrix[y][mi] for y in years if matrix[y][mi]]
        monthly_avg.append(sum(vals) / len(vals) if vals else 0.0)
    return {
        **base,
        "years": years,
        "matrix": {str(y): matrix[y] for y in years},
        "monthlyAvg": monthly_avg,
        "series": series,
    }


def serialize_value_added(d: dict) -> dict:
    """seam.value_added() → ValueAddedAnalysis. Derive years + byLevel from the
    flat series (the seam returns brutaV/procV per year; the view's StackedArea
    wants byLevel.{bruta,processada} = [{y,v}])."""
    series = d.get("series", [])
    by_level = {
        "bruta": [{"y": r["y"], "v": r["brutaV"]} for r in series],
        "processada": [{"y": r["y"], "v": r["procV"]} for r in series],
    }
    return {
        "preview": False,
        "years": [r["y"] for r in series],
        "byLevel": by_level,
        "series": series,
        "nCodes": d.get("n_codes", 0),
    }
