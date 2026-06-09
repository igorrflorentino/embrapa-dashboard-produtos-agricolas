"""The single data seam between the UI and BigQuery.

This is the Python equivalent of the prototype's ``dataStore.datasetFor`` +
``applyFilters``. It does **not** issue its own SQL — it composes the verified
``serving.gateway`` readers (Pushdown Computing: parameterized queries against
the pre-aggregated marts, memoized by ``flask-caching``) into the
``BancoSnapshot`` shapes the views consume.

Golden rule (handoff): the views never change; this layer produces data in the
shape they expect. Every per-banco difference lives here, nowhere else.

M1 scope: the seam serves the PEVS-shaped generic snapshot (products, productTS,
overviewTS, ufData, quality) for the three live bancos. Trade-only adapters
(flow/partner/monthly) and the cross-source builders arrive in M2/M3.
"""

from __future__ import annotations

import functools

import pandas as pd

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild

from . import format as fmt
from .registries import Banco, banco_by_id

# Banco id → the BFF source key (they already align by construction).
_LIVE_SOURCES = {"ibge_pevs", "mdic_comex", "un_comtrade"}

# Trade bancos serve USD-nominal values (the trade marts only carry USD); the
# currency/correction conventions apply fully only to PEVS (BRL-native, with the
# real IPCA/IGP columns). This keeps M1 honest about what each mart holds.
_TRADE = {"mdic_comex", "un_comtrade"}


def effective_value_column(banco: Banco, conv: dict) -> tuple[str, str]:
    """Resolve (column, human_label) for the active convention, with fallback.

    PEVS has the full {yearfx, real_ipca, real_igpm, real_igpdi} × {brl, usd}
    matrix (minus a few combos); trade marts only have USD. We pick the requested
    column when the mart has it, else fall back to the nearest available, so the
    conventions strip never errors on an unmodelled combo (e.g. EUR/CNY).
    """
    if banco.id in _TRADE:
        return "val_yearfx_usd", "Valor (US$ FOB)"
    requested = fmt.monetary_column(conv.get("currency", "BRL"), conv.get("correction", "IPCA"))
    if requested in sqlbuild.ALLOWED_VALUE_COLUMNS:
        return requested, fmt.convention_value_label(conv)
    # Fallback chain: same correction in BRL, then real IPCA BRL.
    brl = fmt.monetary_column("BRL", conv.get("correction", "IPCA"))
    if brl in sqlbuild.ALLOWED_VALUE_COLUMNS:
        label = fmt.convention_value_label({**conv, "currency": "BRL"})
        return brl, f"{label} (moeda indisponível no mart → R$)"
    return "val_real_ipca_brl", "Valor real (IPCA) — R$"


def _years_from_summary(summary: dict | None) -> tuple[int | None, int | None]:
    """Parse (year_start, year_end) from the filter summary's date strings/years."""
    if not summary:
        return None, None

    def _year(key: str) -> int | None:
        v = summary.get(key)
        if not v:
            return None
        try:
            return int(str(v)[:4])
        except (TypeError, ValueError):
            return None

    return _year("startDate"), _year("endDate")


def _basket(summary: dict | None) -> tuple[str, ...]:
    """Product codes selected (empty tuple = no product filter = all)."""
    if not summary:
        return ()
    codes = summary.get("basket")
    return tuple(codes) if codes else ()


def snapshot(banco_id: str, conv: dict, summary: dict | None = None) -> dict:
    """Return the per-banco serving snapshot for the active conventions + filters.

    Keys: products, product_ts, overview_ts, uf_data (None when no geo), quality,
    value_column, value_label. Each value is a pandas DataFrame (or None).
    """
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES:
        return {
            "products": None,
            "product_ts": None,
            "overview_ts": None,
            "uf_data": None,
            "quality": None,
            "value_column": None,
            "value_label": "",
        }

    value_col, value_label = effective_value_column(banco, conv)
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)

    products = gateway.fetch_products(banco_id)
    quality = gateway.fetch_quality_by_source(source=banco_id)

    if banco.id in _TRADE:
        product_ts = gateway.fetch_product_timeseries(
            banco_id, year_start=y0, year_end=y1, codes=codes
        )
        overview_fn = (
            gateway.fetch_comex_overview
            if banco_id == "mdic_comex"
            else gateway.fetch_comtrade_overview
        )
        code_kw = "ncm_codes" if banco_id == "mdic_comex" else "cmd_codes"
        overview_ts = overview_fn(year_start=y0, year_end=y1, **{code_kw: codes})
        uf_data = (
            gateway.fetch_comex_by_uf(year_start=y0, year_end=y1, ncm_codes=codes)
            if banco_id == "mdic_comex"
            else None
        )
        overview_ts = overview_ts.rename(columns={"total_value_usd": "total_value"})
        if uf_data is not None:
            uf_data = uf_data.rename(columns={"total_value_usd": "total_value"})
    else:  # PEVS
        product_ts = gateway.fetch_product_timeseries(
            banco_id, year_start=y0, year_end=y1, codes=codes, value_column=value_col
        )
        overview_ts = gateway.fetch_production_overview(
            year_start=y0, year_end=y1, product_codes=codes, value_column=value_col
        )
        uf_data = gateway.fetch_production_by_uf(
            year_start=y0, year_end=y1, product_codes=codes, value_column=value_col
        )

    return {
        "products": products,
        "product_ts": product_ts,
        "overview_ts": _with_overview_quantities(overview_ts, product_ts),
        "uf_data": uf_data,
        "quality": quality,
        "value_column": value_col,
        "value_label": value_label,
    }


def _with_overview_quantities(overview_ts: pd.DataFrame, product_ts: pd.DataFrame) -> pd.DataFrame:
    """Attach q_mass / q_vol per year, derived from the per-product series.

    ``production_overview`` sums only the value; quantities (which must never be
    summed across families) are aggregated here from ``product_ts`` by family —
    q_mass for the 'massa' family, q_vol for 'volume'.
    """
    if overview_ts is None or overview_ts.empty:
        return overview_ts
    out = overview_ts.copy()
    if product_ts is None or product_ts.empty or "family" not in product_ts.columns:
        out["q_mass"] = None
        out["q_vol"] = None
        return out
    by_fam = (
        product_ts.groupby(["reference_year", "family"])["total_qty_native"]
        .sum()
        .unstack(fill_value=0)
    )
    out = out.set_index("reference_year")
    out["q_mass"] = by_fam.get("massa") if "massa" in by_fam.columns else 0.0
    out["q_vol"] = by_fam.get("volume") if "volume" in by_fam.columns else 0.0
    return out.reset_index()


def source_meta(banco_id: str) -> dict:
    """Provenance row for a banco (backs the page-hero meta), or {} if absent."""
    if banco_id not in _LIVE_SOURCES:
        return {}
    df = gateway.fetch_source_metadata(source=banco_id)
    if df is None or df.empty:
        return {}
    return df.iloc[0].to_dict()


def product_uf_ranking(
    banco_id: str, code: str, conv: dict, summary: dict | None = None
) -> pd.DataFrame | None:
    """Per-UF value for a single product (backs the Perfil do produto ranking)."""
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "geo" not in banco.provides:
        return None
    value_col, _ = effective_value_column(banco, conv)
    y0, y1 = _years_from_summary(summary)
    if banco_id == "mdic_comex":
        return gateway.fetch_comex_by_uf(year_start=y0, year_end=y1, ncm_codes=(code,))
    return gateway.fetch_production_by_uf(
        year_start=y0, year_end=y1, product_codes=(code,), value_column=value_col
    )


# ── Trade adapters (flow / partner / monthly) — M2 ───────────────────────────
# The generic adapters from the contract (previewData.js). Each dispatches by
# banco to the matching gateway reader and returns the raw USD-valued frame; the
# views format/scale. None when the banco lacks the capability (the router gates
# the perspective to "Não se aplica" before these are ever called).


def flow_data(banco_id: str, summary: dict | None = None) -> dict | None:
    """Origin→destination links for the Sankey (backs Fluxos territoriais).

    COMEX: UF de origem → país parceiro. COMTRADE: país reporter → país parceiro.
    Returns {links, origin_label, dest_label} or None when the banco lacks `flow`.
    """
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "flow" not in banco.provides:
        return None
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)
    if banco_id == "mdic_comex":
        links = gateway.fetch_comex_flows(year_start=y0, year_end=y1, ncm_codes=codes)
    else:
        links = gateway.fetch_comtrade_flows(year_start=y0, year_end=y1, cmd_codes=codes)
    dims = banco.dimensions
    return {
        "links": links,
        "origin_label": dims.get("origin", {}).get("label", "Origem"),
        "dest_label": dims.get("dest", {}).get("label", "Destino"),
    }


def partner_data(banco_id: str, summary: dict | None = None) -> pd.DataFrame | None:
    """Partner ranking with export/import split (backs Parceiros comerciais)."""
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "partner" not in banco.provides:
        return None
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)
    if banco_id == "mdic_comex":
        return gateway.fetch_comex_partners(year_start=y0, year_end=y1, ncm_codes=codes)
    return gateway.fetch_comtrade_partners(year_start=y0, year_end=y1, cmd_codes=codes)


def monthly_data(banco_id: str, summary: dict | None = None) -> pd.DataFrame | None:
    """Monthly seasonality value (backs Sazonalidade). COMEX only (monthly grain)."""
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "monthly" not in banco.provides:
        return None
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)
    if banco_id == "mdic_comex":
        return gateway.fetch_comex_seasonality(year_start=y0, year_end=y1, ncm_codes=codes)
    return None


# ── Cross-source comparable annual series — M3 ───────────────────────────────
# One comparable series per (banco, metric), scaled to its DISPLAY_UNIT magnitude
# so series from different bancos compare on one axis (contract §4: two series
# share a Y axis iff their unit strings match). PEVS metrics are computed from the
# production readers (they are not in the gateway cross reader); COMEX/COMTRADE
# come from fetch_cross_series; exp_price is derived value ÷ weight.

CROSS_DISPLAY_UNIT = {
    "ibge_pevs:prod_value": "R$ bi",
    "ibge_pevs:prod_mass": "mil t",
    "ibge_pevs:prod_volume": "mi m³",
    "mdic_comex:exp_value": "US$ bi",
    "mdic_comex:imp_value": "US$ bi",
    "mdic_comex:exp_weight": "mil t",
    "mdic_comex:exp_price": "US$/kg",
    "un_comtrade:exp_value": "US$ bi",
    "un_comtrade:imp_value": "US$ bi",
    "un_comtrade:world_exp": "US$ bi",
}


def _metric_meta(banco: Banco, metric_id: str) -> dict | None:
    return next((m for m in banco.metrics if m["id"] == metric_id), None)


def cross_metric_refs() -> list[dict]:
    """Every (banco, metric) the picker can offer (live bancos with a real series)."""
    refs = []
    for bid in ("ibge_pevs", "mdic_comex", "un_comtrade"):
        b = banco_by_id(bid)
        for m in b.metrics:
            if f"{bid}:{m['id']}" in CROSS_DISPLAY_UNIT:
                refs.append(
                    {
                        "banco": bid,
                        "banco_short": b.short,
                        "metric": m["id"],
                        "label": m["label"],
                        "family": m["family"],
                    }
                )
    return refs


def cross_common_window(refs: list[dict]) -> tuple[int, int]:
    """Intersection of the selected metrics' native coverage (comparable window)."""
    covs = []
    for r in refs:
        b = banco_by_id(r.get("b") or r.get("banco"))
        m = _metric_meta(b, r.get("m") or r.get("metric"))
        if m:
            covs.append(m.get("years", [1986, 2024]))
    if not covs:
        return (1997, 2024)
    y0, y1 = max(c[0] for c in covs), min(c[1] for c in covs)
    if y0 <= y1:
        return (y0, y1)
    return (min(c[0] for c in covs), max(c[1] for c in covs))


def cross_series(
    banco_id: str, metric_id: str, y0: int | None = None, y1: int | None = None
) -> dict | None:
    """Comparable annual series for (banco, metric), in its DISPLAY_UNIT magnitude."""
    key = f"{banco_id}:{metric_id}"
    unit = CROSS_DISPLAY_UNIT.get(key)
    banco = banco_by_id(banco_id)
    metric = _metric_meta(banco, metric_id)
    if unit is None or metric is None or banco_id not in _LIVE_SOURCES:
        return None
    cov = metric.get("years", [1986, 2024])
    yy0, yy1 = (y0 or cov[0]), (y1 or cov[1])
    return {
        "banco": banco_id,
        "banco_short": banco.short,
        "metric": metric_id,
        "key": key,
        "label": metric["label"],
        "unit": unit,
        "family": metric["family"],
        "coverage": cov,
        "points": _cross_points(banco_id, metric_id, yy0, yy1, unit),
    }


def _cross_points(banco_id: str, metric_id: str, y0: int, y1: int, unit: str) -> list[dict]:
    if banco_id == "ibge_pevs":
        if metric_id == "prod_value":
            df = gateway.fetch_production_overview(
                year_start=y0, year_end=y1, value_column="val_real_ipca_brl"
            )
            return [
                {"y": int(r.reference_year), "v": float(r.total_value or 0) / 1e9}
                for r in df.itertuples()
            ]
        fam = "massa" if metric_id == "prod_mass" else "volume"
        scale = 1e3 if metric_id == "prod_mass" else 1e6
        pts = gateway.fetch_product_timeseries(
            "ibge_pevs", year_start=y0, year_end=y1, value_column="val_real_ipca_brl"
        )
        sub = pts[pts["family"] == fam].groupby("reference_year")["total_qty_native"].sum()
        return [{"y": int(y), "v": float(v) / scale} for y, v in sub.items()]
    if metric_id == "exp_price":  # derived: value(US$) ÷ weight(kg) = US$/kg
        val = gateway.fetch_cross_series("mdic_comex:exp_value", year_start=y0, year_end=y1)
        wt = gateway.fetch_cross_series("mdic_comex:exp_weight", year_start=y0, year_end=y1)
        wmap = {int(r.reference_year): float(r.value or 0) for r in wt.itertuples()}
        return [
            {
                "y": int(r.reference_year),
                "v": float(r.value or 0) / (wmap.get(int(r.reference_year)) or 1),
            }
            for r in val.itertuples()
        ]
    df = gateway.fetch_cross_series(f"{banco_id}:{metric_id}", year_start=y0, year_end=y1)
    scale = 1e9 if unit.endswith("bi") else (1e6 if unit == "mil t" else 1.0)
    return [{"y": int(r.reference_year), "v": float(r.value or 0) / scale} for r in df.itertuples()]


# ── Cross-source analytics (crosswalk-joined) — M3b ──────────────────────────
# The four analytical perspectives map the SAME commodity across PEVS / NCM / HS6
# via gold_commodity_crosswalk, then compose existing readers filtered to that
# commodity's codes. Pure composition — no new BFF SQL beyond the crosswalk read.


@functools.lru_cache(maxsize=1)
def _crosswalk_df() -> pd.DataFrame:
    s = get_settings()
    fqn = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_commodity_crosswalk")
    return gateway.run_query(f"select commodity_id, commodity_name, source, code from `{fqn}`", [])


@functools.lru_cache(maxsize=1)
def commodity_catalog() -> dict:
    """commodity_id -> {id, name, pevs[], comex[], comtrade[]} from the crosswalk."""
    cat: dict = {}
    for r in _crosswalk_df().itertuples():
        c = cat.setdefault(
            r.commodity_id,
            {
                "id": r.commodity_id,
                "name": r.commodity_name,
                "pevs": [],
                "comex": [],
                "comtrade": [],
            },
        )
        c[r.source].append(str(r.code))
    return cat


def _codes(commodity_id: str | None, source: str) -> tuple:
    c = commodity_catalog().get(commodity_id) if commodity_id else None
    return tuple(c[source]) if c else ()


def _xyear(metric: str, codes: tuple) -> dict:
    """{year: raw value} from the gateway cross reader for a metric, scoped to codes."""
    df = gateway.fetch_cross_series(metric, codes=codes)
    return {int(r.reference_year): float(r.value or 0) for r in df.itertuples()}


def _pevs_mass_by_year(pevs_codes: tuple) -> dict:
    pts = gateway.fetch_product_timeseries(
        "ibge_pevs", codes=pevs_codes, value_column="val_real_ipca_brl"
    )
    if pts is None or pts.empty:
        return {}
    g = pts.groupby("reference_year")["total_qty_native"].sum()
    return {int(y): float(v) / 1e3 for y, v in g.items()}  # t -> mil t


@functools.lru_cache(maxsize=1)
def _pevs_family_by_commodity() -> dict:
    """commodity_id -> set of PEVS physical-unit families (massa/volume/...).

    Sourced from ``gold_pevs_production.family``. The ``'*'`` key holds every
    family present in PEVS — the basis of the "Cesta completa" / no-filter
    selection, which sums across ALL products. A mass↔weight ratio is only
    meaningful when the PEVS side is purely ``massa``; volume (m³) or mixed
    selections are not — Gold itself warns "NEVER sum qty_base across families".
    """
    s = get_settings()
    pevs = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_pevs_production")
    xwalk = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_commodity_crosswalk")
    q = f"""
        select x.commodity_id as cid, p.family as family
        from `{xwalk}` x
        join `{pevs}` p on x.source = 'pevs' and p.product_code = x.code
        group by cid, family
        union all
        select '*' as cid, family from (select distinct family from `{pevs}`)
    """
    idx: dict = {}
    for r in gateway.run_query(q, []).itertuples():
        idx.setdefault(r.cid, set()).add(r.family)
    return idx


def _is_mass_basis(commodity_id: str | None) -> bool:
    """True iff the PEVS side of this selection is purely mass (t) — the
    precondition for comparing PEVS production against COMEX shipment weight (kg).
    Volume commodities (madeira, m³) and the mixed "Cesta completa" return False."""
    fams = _pevs_family_by_commodity().get(commodity_id or "*", set())
    return fams == {"massa"}


def market_share(commodity_id: str | None) -> dict:
    """BR exports (COMEX) / world exports (COMTRADE), per year + per commodity."""
    br = _xyear("mdic_comex:exp_value", _codes(commodity_id, "comex"))
    world = _xyear("un_comtrade:world_exp", _codes(commodity_id, "comtrade"))
    years = sorted(set(br) & set(world))
    series = [
        {
            "y": y,
            "br": br[y] / 1e9,
            "world": world[y] / 1e9,
            "share": (br[y] / world[y] * 100) if world[y] else 0,
        }
        for y in years
    ]
    by_product = []
    for cid, c in commodity_catalog().items():
        b = _xyear("mdic_comex:exp_value", tuple(c["comex"]))
        w = _xyear("un_comtrade:world_exp", tuple(c["comtrade"]))
        common = sorted(set(b) & set(w))
        if common:
            ly = common[-1]
            by_product.append(
                {"code": cid, "name": c["name"], "share": (b[ly] / w[ly] * 100) if w[ly] else 0}
            )
    by_product.sort(key=lambda x: x["share"], reverse=True)
    return {"unit": "US$ bi", "series": series, "by_product": by_product}


def export_coefficient(commodity_id: str | None) -> dict:
    """Share of each UF's production (PEVS, mass) that is exported (COMEX weight)."""
    if not _is_mass_basis(commodity_id):
        # Volume commodity (m³) or mixed basket: exported-kg ÷ produced-m³ is not a
        # share. Refuse rather than print a dimensionless-nonsense percentage.
        return {
            "unit": "mil t",
            "incompatible": True,
            "by_uf": [],
            "national": {},
            "timeseries": [],
        }
    pevs_codes = _codes(commodity_id, "pevs")
    ncms = _codes(commodity_id, "comex")
    prod = gateway.fetch_production_by_uf(value_column="qty_base", product_codes=pevs_codes)
    exp = gateway.fetch_comex_by_uf(ncm_codes=ncms, flow="export")
    exp_by_uf = {r.state_acronym: float(r.total_weight_kg or 0) / 1e6 for r in exp.itertuples()}
    by_uf = []
    for r in prod.itertuples():
        p = float(r.total_value or 0) / 1e3  # qty_base (t) -> mil t
        e = exp_by_uf.get(r.state_acronym, 0.0)
        by_uf.append(
            {
                "uf": r.state_acronym,
                "name": r.state_name,
                "region": r.region_abbrev,
                "production": p,
                "exportV": e,
                "coefPct": (e / p * 100) if p else 0,
            }
        )
    tp = sum(d["production"] for d in by_uf)
    te = sum(d["exportV"] for d in by_uf)
    national = {"production": tp, "exportV": te, "coefPct": (te / tp * 100) if tp else 0}
    pevs_mass = _pevs_mass_by_year(pevs_codes)
    exp_mass = {y: v / 1e6 for y, v in _xyear("mdic_comex:exp_weight", ncms).items()}
    ts = sorted(set(pevs_mass) & set(exp_mass))
    timeseries = [
        {"y": y, "v": (exp_mass[y] / pevs_mass[y] * 100) if pevs_mass[y] else 0} for y in ts
    ]
    return {"unit": "mil t", "by_uf": by_uf, "national": national, "timeseries": timeseries}


def price_spread(commodity_id: str | None) -> dict:
    """Farm-gate implied price (PEVS, US$/kg) vs FOB export price (COMEX, US$/kg)."""
    if not _is_mass_basis(commodity_id):
        # Gate price = PEVS value ÷ PEVS quantity; for a volume commodity that is
        # US$/m³, not the US$/kg the FOB price uses — markup/spread would be invalid.
        return {"unit": "US$/kg", "incompatible": True, "series": []}
    ncms = _codes(commodity_id, "comex")
    val = _xyear("mdic_comex:exp_value", ncms)
    wt = _xyear("mdic_comex:exp_weight", ncms)
    fob = {y: (val[y] / wt[y]) for y in (set(val) & set(wt)) if wt[y]}  # US$/kg
    pts = gateway.fetch_product_timeseries(
        "ibge_pevs", codes=_codes(commodity_id, "pevs"), value_column="val_yearfx_usd"
    )
    gate = {}
    if pts is not None and not pts.empty:
        g = pts.groupby("reference_year").agg(
            v=("total_value", "sum"), q=("total_qty_native", "sum")
        )
        gate = {int(y): (row.v / (row.q * 1000)) if row.q else 0 for y, row in g.iterrows()}
    years = sorted(set(fob) & set(gate))
    series = [
        {
            "y": y,
            "fob": fob[y],
            "gate": gate[y],
            "spread": fob[y] - gate[y],
            "markup": (fob[y] / gate[y]) if gate[y] else 0,
        }
        for y in years
    ]
    return {"unit": "US$/kg", "series": series}


def trade_mirror(commodity_id: str | None) -> dict:
    """The same BR exports seen by MDIC (COMEX) vs UN Comtrade (reporter = Brazil)."""
    mdic = {
        y: v / 1e9 for y, v in _xyear("mdic_comex:exp_value", _codes(commodity_id, "comex")).items()
    }
    comtrade = {
        y: v / 1e9
        for y, v in _xyear("un_comtrade:exp_value", _codes(commodity_id, "comtrade")).items()
    }
    years = sorted(set(mdic) & set(comtrade))
    series = [{"y": y, "mdic": mdic[y], "comtrade": comtrade[y]} for y in years]
    discrepancy = [
        {
            "y": d["y"],
            "v": abs(d["mdic"] - d["comtrade"]) / (((d["mdic"] + d["comtrade"]) / 2) or 1) * 100,
        }
        for d in series
    ]
    return {"unit": "US$ bi", "series": series, "discrepancy": discrepancy}
