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
        {"code": str(r.code), "name": r.name, "unit": r.unit, "family": _fam(r.family)}
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
