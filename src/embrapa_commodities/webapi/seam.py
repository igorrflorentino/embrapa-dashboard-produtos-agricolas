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

import pandas as pd
from google.api_core.exceptions import NotFound

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache

from . import format as fmt
from .registries import Banco, banco_by_id

# Banco id → the BFF source key (they already align by construction).
_LIVE_SOURCES = {"ibge_pevs", "ibge_pam", "mdic_comex", "un_comtrade"}

# Trade bancos are USD-NATIVE (customs values declared in US$ — FOB exports, CIF
# imports for COMTRADE), but the serving marts now carry the SAME currency matrix
# as PEVS (val_yearfx_{brl,usd,eur} + val_real_{ipca,igpm,igpdi}_{brl,usd,eur} —
# the REAL year-FX / deflated values Gold computes), so a BRL/EUR display serves
# the real column instead of the frontend cross-converting USD via a mock FX rate.
_TRADE = {"mdic_comex", "un_comtrade"}


def _trade_valuation_note(banco: Banco) -> str:
    """The US$-source valuation basis a trade banco's value label must state.

    COMTRADE sums both flows where exports are FOB and imports CIF; COMEX is FOB
    for both. The note is appended to the convention label so a researcher reading
    a BRL/EUR figure still knows it is the year-FX conversion of the customs US$.
    """
    if banco.id == "un_comtrade":
        return "FOB exportação / CIF importação"
    return "FOB"


def effective_value_column(banco: Banco, conv: dict) -> tuple[str, str]:
    """Resolve (column, human_label) for the active convention, with fallback.

    Every live mart now carries the full {yearfx, real_ipca, real_igpm, real_igpdi}
    × {brl, usd, eur} matrix (minus the IGP-M/IGP-DI × USD combos the allowlist
    deliberately omits). We pick the requested column when the mart has it, else
    fall back to the nearest available, so the conventions strip never errors on an
    unmodelled combo (e.g. USD + IGP-M).

    For trade bancos the values are the year-FX conversion of US$ customs figures,
    so the label keeps the FOB/CIF basis note — but the figure IS in the requested
    currency (no client-side mock FX). The default request (empty conv) resolves to
    BRL·IPCA via :func:`embrapa_commodities.webapi.format.monetary_column`; trade
    callers that want the US$-native default pass ``{"currency": "USD",
    "correction": "Nominal"}``.
    """
    requested = fmt.monetary_column(conv.get("currency", "BRL"), conv.get("correction", "IPCA"))
    if banco.id in _TRADE:
        note = _trade_valuation_note(banco)
        if requested in sqlbuild.ALLOWED_VALUE_COLUMNS:
            return requested, f"{fmt.convention_value_label(conv)} · {note}"
        # Fallback chain (same as PEVS): same correction in BRL, then real IPCA BRL —
        # all REAL columns, never a mock conversion.
        brl = fmt.monetary_column("BRL", conv.get("correction", "IPCA"))
        if brl in sqlbuild.ALLOWED_VALUE_COLUMNS:
            label = fmt.convention_value_label({**conv, "currency": "BRL"})
            return brl, f"{label} (moeda indisponível no mart → R$) · {note}"
        return "val_real_ipca_brl", f"Valor real (IPCA) — R$ · {note}"
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


def _states(summary: dict | None) -> tuple[str, ...]:
    """Origin-UF acronyms selected (empty tuple = no UF filter = all).

    The frontend's filter summary carries the UF selection under ``states``
    (``null``/absent = all · ``[]`` = none). Only the COMEX-origin readers can
    honour it (their mart carries ``state_acronym``); other trade grains surface
    it as not-applicable rather than silently dropping it.
    """
    if not summary:
        return ()
    states = summary.get("states")
    return tuple(states) if states else ()


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
            "uf_yearly": None,
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
        # value_col is the currency×correction column the conventions resolve to —
        # now a REAL BRL/USD/EUR (or deflated) column the trade marts carry, so the
        # snapshot value is served IN the requested currency instead of always USD
        # (which the frontend used to cross-convert via a mock FX rate).
        product_ts = gateway.fetch_product_timeseries(
            banco_id, year_start=y0, year_end=y1, codes=codes, value_column=value_col
        )
        overview_fn = (
            gateway.fetch_comex_overview
            if banco_id == "mdic_comex"
            else gateway.fetch_comtrade_overview
        )
        code_kw = "ncm_codes" if banco_id == "mdic_comex" else "cmd_codes"
        overview_ts = overview_fn(
            year_start=y0, year_end=y1, value_column=value_col, **{code_kw: codes}
        )
        uf_data = (
            gateway.fetch_comex_by_uf(
                year_start=y0, year_end=y1, ncm_codes=codes, value_column=value_col
            )
            if banco_id == "mdic_comex"
            else None
        )
        uf_yearly = (
            gateway.fetch_comex_by_uf_yearly(
                year_start=y0, year_end=y1, ncm_codes=codes, value_column=value_col
            )
            if banco_id == "mdic_comex"
            else None
        )
        overview_ts = overview_ts.rename(columns={"total_value_usd": "total_value"})
        if uf_data is not None:
            uf_data = uf_data.rename(columns={"total_value_usd": "total_value"})
        if uf_yearly is not None:
            uf_yearly = uf_yearly.rename(columns={"total_value_usd": "total_value"})
    else:  # PEVS-shaped (ibge_pevs, ibge_pam): production marts, BRL-native value matrix
        product_ts = gateway.fetch_product_timeseries(
            banco_id, year_start=y0, year_end=y1, codes=codes, value_column=value_col
        )
        overview_ts = gateway.fetch_production_overview(
            year_start=y0, year_end=y1, product_codes=codes, value_column=value_col, source=banco_id
        )
        uf_data = gateway.fetch_production_by_uf(
            year_start=y0, year_end=y1, product_codes=codes, value_column=value_col, source=banco_id
        )
        uf_yearly = gateway.fetch_production_by_uf_yearly(
            year_start=y0, year_end=y1, product_codes=codes, value_column=value_col, source=banco_id
        )

    return {
        "products": products,
        "product_ts": product_ts,
        "overview_ts": _with_overview_quantities(overview_ts, product_ts),
        "uf_data": uf_data,
        "uf_yearly": uf_yearly,
        "quality": quality,
        "quality_ts": gateway.fetch_quality_timeseries(banco_id),
        "quality_by_product": gateway.fetch_quality_by_product(banco_id),
        "value_column": value_col,
        "value_label": value_label,
    }


def _with_overview_quantities(overview_ts: pd.DataFrame, product_ts: pd.DataFrame) -> pd.DataFrame:
    """Attach q_mass / q_vol per year, derived from the per-product series.

    ``production_overview`` sums only the value; quantities (which must never be
    summed across families) are aggregated here from ``product_ts`` by family —
    q_mass for the 'massa' family, q_vol for 'volume'. Sums ``total_qty_base``
    (t / m³), NOT the native quantity: trade sources mix kg- and t-native codes
    inside the 'massa' family, so only the base unit is summable (for PEVS/PAM
    native == base, so nothing changes there).
    """
    if overview_ts is None or overview_ts.empty:
        return overview_ts
    out = overview_ts.copy()
    if product_ts is None or product_ts.empty or "family" not in product_ts.columns:
        out["q_mass"] = None
        out["q_vol"] = None
        return out
    by_fam = (
        product_ts.groupby(["reference_year", "family"])["total_qty_base"]
        .sum()
        .unstack(fill_value=0)
    )
    out = out.set_index("reference_year")
    out["q_mass"] = by_fam.get("massa") if "massa" in by_fam.columns else 0.0
    out["q_vol"] = by_fam.get("volume") if "volume" in by_fam.columns else 0.0
    return out.reset_index()


# Monthly-sourced bancos whose latest year can be PARTIAL (a year with < 12 months
# of published data). Only COMEX carries a month grain in serving; COMTRADE/PEVS/PAM
# are annual, so their latest year is always complete by construction.
_MONTHLY_SOURCES = {"mdic_comex"}


def _latest_year_completeness(banco_id: str, year_end: int | None) -> dict:
    """Whether ``year_end`` (the latest covered year) is COMPLETE, for YoY honesty.

    A monthly-sourced banco (COMEX) publishes the current year month-by-month, so its
    latest year is usually PARTIAL — a frontend YoY that compares it against a full
    prior year over-reads as a crash/boom (audit finding: COMEX 2026 ≈ 39% of 2025
    showed a spurious −41%). The frontend can't tell a year is partial from annual
    totals alone, so we expose the signal here, derived from the monthly mart:

      * ``monthsInLatestYear`` — distinct months present in ``year_end`` (None for an
        annual banco, which has no month grain).
      * ``latestYearComplete`` — True iff that year has all 12 months (always True for
        an annual banco — its latest year is complete by construction).
      * ``latestCompleteYear`` — the most recent FULLY-covered year (``year_end`` when
        complete, else ``year_end - 1``), so the frontend can anchor YoY on it.

    Annual bancos return the trivially-complete shape without any extra query.
    """
    if banco_id not in _MONTHLY_SOURCES or year_end is None:
        return {
            "months_in_latest_year": None,
            "latest_year_complete": True,
            "latest_complete_year": year_end,
        }
    df = gateway.fetch_comex_months_per_year()
    months_by_year = (
        {int(r.reference_year): int(r.n_months) for r in df.itertuples()}
        if df is not None and not df.empty
        else {}
    )
    n_months = months_by_year.get(int(year_end))
    complete = n_months == 12
    return {
        "months_in_latest_year": n_months,
        "latest_year_complete": complete,
        # Fall back to the prior year only when the latest is genuinely partial AND
        # we actually observed its month count (n_months is not None).
        "latest_complete_year": year_end if complete else (year_end - 1),
    }


def source_meta(banco_id: str) -> dict:
    """Provenance row for a banco (backs the page-hero meta), or {} if absent.

    Augmented with the latest-year completeness signal (months_in_latest_year /
    latest_year_complete / latest_complete_year) so the frontend can compute an
    honest YoY for monthly-sourced bancos whose latest year is still partial.
    """
    if banco_id not in _LIVE_SOURCES:
        return {}
    df = gateway.fetch_source_metadata(source=banco_id)
    if df is None or df.empty:
        return {}
    meta = df.iloc[0].to_dict()
    year_end = meta.get("year_end")
    try:
        year_end = int(year_end) if year_end is not None else None
    except (TypeError, ValueError):
        year_end = None
    meta.update(_latest_year_completeness(banco_id, year_end))
    _apply_banco_metadata(meta, banco_id)
    return meta


def banco_metadata_overrides(banco_id: str) -> dict:
    """Operator-set maturity/coverage overrides for a banco; empty dict when the
    override table is absent (none configured) or the banco has no row. Any OTHER
    error propagates — a transient BQ/permission fault must NOT silently erase a
    deliberate flip (e.g. beta→estavel) back to the registry default."""
    try:
        df = gateway.fetch_banco_metadata(banco_id)
    except NotFound:
        return {}
    if df is None or df.empty:
        return {}
    row = df.iloc[0].to_dict()
    # Keep only set columns: a NULL/NaN override means "use the registry default".
    return {
        k: v
        for k, v in row.items()
        if v is not None and not (isinstance(v, float) and pd.isna(v))
    }


def _apply_banco_metadata(meta: dict, banco_id: str) -> None:
    """Overlay the editable override row over the registry Banco defaults, writing
    maturity/maturity_note/maturity_date/cobertura into ``meta``. The registry stays
    the source of truth; the override table only carries deliberate per-field edits."""
    banco = banco_by_id(banco_id)
    ov = banco_metadata_overrides(banco_id)
    meta["maturity"] = ov.get("maturity") or (banco.maturity if banco else None)
    meta["maturity_note"] = ov.get("maturity_note", banco.maturity_note if banco else None)
    meta["maturity_date"] = ov.get("maturity_date", banco.maturity_date if banco else None)
    cobertura = dict(banco.cobertura) if banco and banco.cobertura else {}
    for col, key in (
        ("cobertura_years", "years"),
        ("cobertura_atualizacao", "atualizacao"),
        ("cobertura_granularidade", "granularidade"),
    ):
        if ov.get(col):
            cobertura[key] = ov[col]
    meta["cobertura"] = cobertura or None


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
        return gateway.fetch_comex_by_uf(
            year_start=y0, year_end=y1, ncm_codes=(code,), value_column=value_col
        )
    return gateway.fetch_production_by_uf(
        year_start=y0, year_end=y1, product_codes=(code,), value_column=value_col, source=banco_id
    )


def productivity(banco_id: str, crop: str | None, summary: dict | None = None) -> dict | None:
    """Área × rendimento for one crop (backs ViewProductivity).

    Returns ``{crops, active, active_name, rows}`` where ``rows`` is the per-(year,
    UF) production + harvested-area frame for the active crop, or ``None`` when the
    banco lacks the ``yield`` capability (the router gates the perspective before
    this is reached). The serializer recomputes yield (= prod_kg / area_ha) and
    shapes the national series + per-UF latest-year geography.
    """
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "yield" not in banco.provides:
        return None
    crops = _productivity_crops(gateway.fetch_products(banco_id))
    if not crops:
        return None
    codes = {c["code"] for c in crops}
    active = crop if (crop and crop in codes) else crops[0]["code"]
    active_name = next((c["name"] for c in crops if c["code"] == active), active)
    y0, y1 = _years_from_summary(summary)
    return {
        "crops": crops,
        "active": active,
        "active_name": active_name,
        "rows": gateway.fetch_productivity(active, source=banco_id, year_start=y0, year_end=y1),
    }


def _productivity_crops(products: pd.DataFrame | None) -> list[dict]:
    """Shape the products frame into [{code, name}] (name falls back to code)."""
    if products is None or products.empty:
        return []
    return [
        {
            "code": str(r.code),
            "name": (r.name if isinstance(r.name, str) and r.name else str(r.code)),
        }
        for r in products.itertuples()
    ]


# ── Trade adapters (flow / partner / monthly) — M2 ───────────────────────────
# The generic adapters from the contract (previewData.js). Each dispatches by
# banco to the matching gateway reader and returns the raw USD-valued frame; the
# views format/scale. None when the banco lacks the capability (the router gates
# the perspective to "Não se aplica" before these are ever called).


def flow_data(banco_id: str, summary: dict | None = None) -> dict | None:
    """Origin→destination links for the Sankey (backs Fluxos territoriais).

    COMEX: UF de origem → país parceiro. COMTRADE: país reporter → país parceiro.
    Returns {links, origin_label, dest_label} or None when the banco lacks `flow`.
    The active UF (``states``) filter narrows the COMEX origin; COMTRADE's origin is
    a reporter country (no UF column), so the UF selection does not reach its reader
    — the frontend producer surfaces that as an honest "não se aplica" note.
    """
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "flow" not in banco.provides:
        return None
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)
    if banco_id == "mdic_comex":
        # Exports only: SG_UF_NCM is the UF *of the product*, so on import rows
        # the real direction is country→UF — summing them into the directed
        # 'UF de origem → país parceiro' links would inflate and mislabel them.
        links = gateway.fetch_comex_flows(
            year_start=y0, year_end=y1, ncm_codes=codes, flow="export", uf_codes=_states(summary)
        )
    else:
        links = gateway.fetch_comtrade_flows(year_start=y0, year_end=y1, cmd_codes=codes)
    dims = banco.dimensions
    return {
        "links": links,
        "origin_label": dims.get("origin", {}).get("label", "Origem"),
        "dest_label": dims.get("dest", {}).get("label", "Destino"),
    }


def partner_data(banco_id: str, summary: dict | None = None) -> pd.DataFrame | None:
    """Partner ranking with export/import split (backs Parceiros comerciais).

    The active UF (``states``) filter narrows the COMEX partner ranking to those
    origin UFs (``state_acronym``). COMTRADE has no origin-UF column (its origin is
    a reporter country), so the UF selection does not reach its reader — the
    frontend producer surfaces that as an honest "não se aplica" note.
    """
    banco = banco_by_id(banco_id)
    if banco_id not in _LIVE_SOURCES or "partner" not in banco.provides:
        return None
    y0, y1 = _years_from_summary(summary)
    codes = _basket(summary)
    if banco_id == "mdic_comex":
        return gateway.fetch_comex_partners(
            year_start=y0, year_end=y1, ncm_codes=codes, uf_codes=_states(summary)
        )
    return gateway.fetch_comtrade_partners(year_start=y0, year_end=y1, cmd_codes=codes)


def monthly_data(banco_id: str, summary: dict | None = None) -> pd.DataFrame | None:
    """Monthly seasonality value (backs Sazonalidade). COMEX only (monthly grain).

    The seasonality mart (``serving_comex_seasonality``) collapses UF away — its
    grain is (year × month × flow × NCM) — so a UF (``states``) filter cannot be
    honoured here. The frontend producer surfaces it as an honest "não se aplica"
    note rather than the seam silently dropping it; the basket + year window apply.
    """
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
        return _pevs_cross_points(metric_id, y0, y1)
    if metric_id == "exp_price":
        return _exp_price_cross_points(y0, y1)
    df = gateway.fetch_cross_series(f"{banco_id}:{metric_id}", year_start=y0, year_end=y1)
    scale = 1e9 if unit.endswith("bi") else (1e6 if unit == "mil t" else 1.0)
    return [{"y": int(r.reference_year), "v": float(r.value or 0) / scale} for r in df.itertuples()]


def _pevs_cross_points(metric_id: str, y0: int, y1: int) -> list[dict]:
    """PEVS cross points: value (÷1e9) or per-family native quantity (÷1e3 / ÷1e6)."""
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


def _exp_price_cross_points(y0: int, y1: int) -> list[dict]:
    """Derived COMEX export price: value(US$) ÷ weight(kg) = US$/kg."""
    val = gateway.fetch_cross_series("mdic_comex:exp_value", year_start=y0, year_end=y1)
    wt = gateway.fetch_cross_series("mdic_comex:exp_weight", year_start=y0, year_end=y1)
    wmap = {int(r.reference_year): float(r.value or 0) for r in wt.itertuples()}
    # A year with no (or zero) weight has no defined price: emit None (a gap
    # in the chart) — NEVER divide by 1, which would plot the year's raw
    # total US$ value as a 'US$/kg' point.
    return [
        {
            "y": int(r.reference_year),
            "v": (
                float(r.value or 0) / wmap[int(r.reference_year)]
                if wmap.get(int(r.reference_year))
                else None
            ),
        }
        for r in val.itertuples()
    ]


# ── Cross-source analytics (crosswalk-joined) — M3b ──────────────────────────
# The four analytical perspectives map the SAME commodity across PEVS / NCM / HS6
# via gold_commodity_crosswalk, then compose existing readers filtered to that
# commodity's codes. Pure composition — no new BFF SQL beyond the crosswalk read.
#
# The crosswalk/catalog reads below are memoized with the SAME flask-caching TTL
# the gateway mart reads use (CACHE_DEFAULT_TIMEOUT) — NOT functools.lru_cache:
# the crosswalk and the Gold families it joins are rebuilt by the nightly dbt
# run, so a long-lived Cloud Run instance must converge to the fresh catalog
# within the TTL instead of serving a stale one for its whole process lifetime.


@cache.memoize()
def _crosswalk_df() -> pd.DataFrame:
    s = get_settings()
    fqn = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_commodity_crosswalk")
    return gateway.run_query(f"select commodity_id, commodity_name, source, code from `{fqn}`", [])


@cache.memoize()
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


@cache.memoize()
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


def _market_share_series(comex_codes: tuple, comtrade_codes: tuple) -> list[dict]:
    """Yearly BR-export ÷ world-export share (US$ bi) over the common-year window."""
    br = _xyear("mdic_comex:exp_value", comex_codes)
    world = _xyear("un_comtrade:world_exp", comtrade_codes)
    return [
        {
            "y": y,
            "br": br[y] / 1e9,
            "world": world[y] / 1e9,
            "share": (br[y] / world[y] * 100) if world[y] else 0,
        }
        for y in sorted(set(br) & set(world))
    ]


def _market_share_latest(comex_codes: tuple, comtrade_codes: tuple) -> float | None:
    """Latest common-year BR ÷ world share (%), or None when there is no overlap."""
    b = _xyear("mdic_comex:exp_value", comex_codes)
    w = _xyear("un_comtrade:world_exp", comtrade_codes)
    common = sorted(set(b) & set(w))
    if not common:
        return None
    ly = common[-1]
    return (b[ly] / w[ly] * 100) if w[ly] else 0


def market_share(commodity_id: str | None) -> dict:
    """BR exports (COMEX) / world exports (COMTRADE), per year + per commodity."""
    comex_codes = _codes(commodity_id, "comex")
    comtrade_codes = _codes(commodity_id, "comtrade")
    series = []
    # Guard (mirrors market_nature): a scoped commodity missing codes for either
    # source must yield an EMPTY series — an empty tuple means "no filter" to the
    # readers, which would silently serve the ALL-commodities totals as if scoped.
    if not commodity_id or (comex_codes and comtrade_codes):
        series = _market_share_series(comex_codes, comtrade_codes)
    by_product = []
    for cid, c in commodity_catalog().items():
        if not (c["comex"] and c["comtrade"]):
            continue  # same guard per commodity — never the unscoped totals
        share = _market_share_latest(tuple(c["comex"]), tuple(c["comtrade"]))
        if share is not None:
            by_product.append({"code": cid, "name": c["name"], "share": share})
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
    if commodity_id and not (pevs_codes and ncms):
        # Commodity has no codes for a needed source: empty payload, never the
        # unscoped ALL-commodities totals (empty codes mean "no filter").
        return {"unit": "mil t", "by_uf": [], "national": {}, "timeseries": []}
    pevs_mass = _pevs_mass_by_year(pevs_codes)
    exp_mass = {y: v / 1e6 for y, v in _xyear("mdic_comex:exp_weight", ncms).items()}
    ts = sorted(set(pevs_mass) & set(exp_mass))
    timeseries = [
        {"y": y, "v": (exp_mass[y] / pevs_mass[y] * 100) if pevs_mass[y] else 0} for y in ts
    ]
    if not ts:
        return {"unit": "mil t", "by_uf": [], "national": {}, "timeseries": []}
    # The by-UF/national ratios must compare the SAME window on both sides:
    # PEVS starts in 1986 but COMEX only in 1997, so unbounded cumulative sums
    # would systematically understate coefPct (and disagree with the timeseries,
    # which already intersects the two sources' years).
    by_uf = _export_coef_by_uf(pevs_codes, ncms, ts[0], ts[-1])
    return {
        "unit": "mil t",
        "by_uf": by_uf,
        "national": _export_coef_national(by_uf),
        "timeseries": timeseries,
    }


def _export_coef_by_uf(pevs_codes: tuple, ncms: tuple, y0: int, y1: int) -> list[dict]:
    """Per-UF production (mil t) vs exported weight (mil t) and their coefficient.

    Both readers are window-CUMULATIVE (``latest_year_only=False``): the coefficient
    is exported-over-window ÷ produced-over-window across the SAME ``[y0, y1]``
    common-year intersection, NOT a single latest-year ratio (that is the snapshot
    choropleth's job). A single-year ratio would also reintroduce the year-window
    mismatch the cumulative sums were built to avoid.
    """
    prod = gateway.fetch_production_by_uf(
        year_start=y0,
        year_end=y1,
        value_column="qty_base",
        product_codes=pevs_codes,
        latest_year_only=False,
    )
    exp = gateway.fetch_comex_by_uf(
        year_start=y0, year_end=y1, ncm_codes=ncms, flow="export", latest_year_only=False
    )
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
    return by_uf


def _export_coef_national(by_uf: list[dict]) -> dict:
    """Aggregate the per-UF rows into the national production/export/coefficient."""
    tp = sum(d["production"] for d in by_uf)
    te = sum(d["exportV"] for d in by_uf)
    return {"production": tp, "exportV": te, "coefPct": (te / tp * 100) if tp else 0}


def _fob_price_by_year(ncms: tuple) -> dict:
    """FOB export unit price (US$/kg) = COMEX value ÷ weight, per common year."""
    val = _xyear("mdic_comex:exp_value", ncms)
    wt = _xyear("mdic_comex:exp_weight", ncms)
    return {y: (val[y] / wt[y]) for y in (set(val) & set(wt)) if wt[y]}


def _gate_price_by_year(pevs_codes: tuple) -> dict:
    """Farm-gate implied price (US$/kg) = PEVS value ÷ (quantity × 1000), per year."""
    pts = gateway.fetch_product_timeseries(
        "ibge_pevs", codes=pevs_codes, value_column="val_yearfx_usd"
    )
    if pts is None or pts.empty:
        return {}
    g = pts.groupby("reference_year").agg(v=("total_value", "sum"), q=("total_qty_native", "sum"))
    return {int(y): (row.v / (row.q * 1000)) if row.q else 0 for y, row in g.iterrows()}


def price_spread(commodity_id: str | None) -> dict:
    """Farm-gate implied price (PEVS, US$/kg) vs FOB export price (COMEX, US$/kg)."""
    if not _is_mass_basis(commodity_id):
        # Gate price = PEVS value ÷ PEVS quantity; for a volume commodity that is
        # US$/m³, not the US$/kg the FOB price uses — markup/spread would be invalid.
        return {"unit": "US$/kg", "incompatible": True, "series": []}
    ncms = _codes(commodity_id, "comex")
    if commodity_id and not ncms:
        # No NCM codes for this commodity: empty payload, never the unscoped
        # ALL-commodities FOB price (empty codes mean "no filter" to the reader).
        return {"unit": "US$/kg", "series": []}
    fob = _fob_price_by_year(ncms)
    gate = _gate_price_by_year(_codes(commodity_id, "pevs"))
    series = [
        {
            "y": y,
            "fob": fob[y],
            "gate": gate[y],
            "spread": fob[y] - gate[y],
            "markup": (fob[y] / gate[y]) if gate[y] else 0,
        }
        for y in sorted(set(fob) & set(gate))
    ]
    return {"unit": "US$/kg", "series": series}


def trade_mirror(commodity_id: str | None) -> dict:
    """The same BR exports seen by MDIC (COMEX) vs UN Comtrade (reporter = Brazil)."""
    comex_codes = _codes(commodity_id, "comex")
    comtrade_codes = _codes(commodity_id, "comtrade")
    if commodity_id and not (comex_codes and comtrade_codes):
        # Missing codes for one side: empty payload, never a "mirror" of the
        # unscoped ALL-commodities totals (empty codes mean "no filter").
        return {"unit": "US$ bi", "series": [], "discrepancy": []}
    mdic = {y: v / 1e9 for y, v in _xyear("mdic_comex:exp_value", comex_codes).items()}
    comtrade = {y: v / 1e9 for y, v in _xyear("un_comtrade:exp_value", comtrade_codes).items()}
    # Third line: every OTHER country's declaration of what it imported FROM Brazil
    # (partner = Brazil on import rows) — the mirror view's "Reportado pelos parceiros".
    partners = {y: v / 1e9 for y, v in _xyear("un_comtrade:partner_exp", comtrade_codes).items()}
    years = sorted(set(mdic) & set(comtrade))
    series = [
        {"y": y, "mdic": mdic[y], "comtrade": comtrade[y], "partners": partners.get(y)}
        for y in years
    ]
    discrepancy = [
        {
            "y": d["y"],
            "v": abs(d["mdic"] - d["comtrade"]) / (((d["mdic"] + d["comtrade"]) / 2) or 1) * 100,
        }
        for d in series
    ]
    return {"unit": "US$ bi", "series": series, "discrepancy": discrepancy}


# ── Curadoria — per-code industrialization curation + value-added analysis ─────
# The editor classifies each Gold CODE (per source) as bruta/processada; the
# value-added analysis splits COMEX exports by that curated level. The READ side
# degrades gracefully when dim_code_industrialization_scd2 is not built yet (gate
# off / fresh project): every code surfaces as "a classificar" instead of erroring.
# Writes go through the verified BFF writer (IAP author capture).

CUR_LEVELS = ("bruta", "processada", "misturado")


@cache.memoize()
def _code_to_commodity() -> dict:
    """{(source, code) -> commodity_id} reverse index of the crosswalk, for
    grouping the worklist by commodity."""
    idx: dict = {}
    for cid, c in commodity_catalog().items():
        for src_key, source in (
            ("pevs", "ibge_pevs"),
            ("comex", "mdic_comex"),
            ("comtrade", "un_comtrade"),
        ):
            for code in c.get(src_key, ()):
                idx[(source, str(code))] = cid
    return idx


def curator_emails() -> set[str]:
    """Lowercased curator emails from the allowlist table; empty set when the
    table is absent (allowlist not configured) — so routes fall back to "any
    IAP-authenticated caller may curate". Any OTHER error propagates (a transient
    BQ/permission fault must NOT silently widen the gate to everyone)."""
    try:
        df = gateway.fetch_curators()
    except NotFound:
        return set()
    if df is None or df.empty:
        return set()
    return {str(e).strip().lower() for e in df["email"] if e}


def _current_code_levels() -> dict:
    """{(source, code): level} from the SCD2 view; {} when the view is absent
    (curation not enabled in this dataset yet) — so the worklist still renders."""
    try:
        df = gateway.fetch_current_code_industrialization()
    except NotFound:
        # The SCD2 view genuinely doesn't exist yet (curation not enabled) — render
        # the worklist empty. Any OTHER error (transient BQ, permissions) must
        # propagate, not be masked as "not built yet".
        return {}
    if df is None or df.empty:
        return {}
    return {(r.source, str(r.code)): r.industrialization_level for r in df.itertuples()}


def _worklist_rows_for_source(src: str, levels: dict, cmap: dict, catalog: dict) -> list[dict]:
    """The per-source code rows: each Gold code ⟕ its level + crosswalk commodity."""
    products = gateway.fetch_products(src)
    if products is None or products.empty:
        return []
    rows = []
    for p in products.itertuples():
        code = str(p.code)
        cid = cmap.get((src, code))
        rows.append(
            {
                "source": src,
                "code": code,
                "name": str(getattr(p, "name", code) or code),
                "commodity": cid,
                "commodity_name": catalog.get(cid, {}).get("name") if cid else None,
                "level": levels.get((src, code)),
            }
        )
    return rows


def curation_worklist() -> dict:
    """The LEFT JOIN: Gold DISTINCT codes (per live source) ⟕ current levels.

    Each code carries its curated level or None ("a classificar"), plus the
    commodity it maps to (via the crosswalk) for grouping. Pure reads; safe before
    the SCD2 view exists (all codes then read as unclassified).
    """
    levels = _current_code_levels()
    cmap = _code_to_commodity()
    catalog = commodity_catalog()
    rows = []
    for src in ("ibge_pevs", "mdic_comex", "un_comtrade"):
        if src in _LIVE_SOURCES:
            rows.extend(_worklist_rows_for_source(src, levels, cmap, catalog))
    classified = sum(1 for r in rows if r["level"])
    by_level = {lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in CUR_LEVELS}
    return {
        "rows": rows,
        "total": len(rows),
        "classified": classified,
        "pending": len(rows) - classified,
        "by_level": by_level,
    }


def record_code_level(source: str, code: str, level: str, change_id: str | None = None) -> dict:
    """Append one per-code classification edit. The author comes from the request's
    IAP header (dev fallback per config). ``change_id`` is the optional client
    idempotency key (a retried save reusing it is a no-op). Wraps the verified
    BFF writer."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import curation

    headers = dict(request.headers) if has_request_context() else {}
    return curation.record_code_industrialization(source, code, level, headers, change_id=change_id)


def value_added(commodity_id: str | None = None) -> dict:
    """COMEX exports split by the curated industrialization level over the years.

    For each mdic_comex code currently classified bruta/processada, sum its annual
    export value (US$ bi) + weight (mil t) into that level. Real data, but empty
    until codes are classified in Curadoria. ``commodity_id`` optionally scopes to
    one crosswalk commodity. Composes existing readers — no new BFF SQL.

    Set-based: ONE value + ONE weight query per level (the reader's ``codes``
    filter is an ``IN UNNEST`` over the whole level), so the request cost stays
    flat as curators classify more codes — never 2 BigQuery round-trips per code.
    """
    by_level = _value_added_codes_by_level(commodity_id)
    acc, n = _value_added_accumulate(by_level)
    series = [_value_added_series_point(y, acc[y]) for y in sorted(acc)]
    return {"series": series, "n_codes": n}


def _value_added_codes_by_level(commodity_id: str | None) -> dict[str, list[str]]:
    """Group currently-classified COMEX codes into {bruta, processada} (scoped)."""
    scope = set(_codes(commodity_id, "comex")) if commodity_id else None
    by_level: dict[str, list[str]] = {"bruta": [], "processada": []}
    for (src, code), lvl in _current_code_levels().items():
        if src != "mdic_comex" or lvl not in by_level:
            continue
        if scope is not None and code not in scope:
            continue
        by_level[lvl].append(code)
    return by_level


def _value_added_accumulate(by_level: dict[str, list[str]]) -> tuple[dict, int]:
    """Sum export value (US$ bi) + weight (mil t) per year per level; (acc, n_codes).

    ONE value + ONE weight query per level (the reader's ``codes`` filter is an
    ``IN UNNEST`` over the whole level), so the cost stays flat as more codes are
    classified — never 2 BigQuery round-trips per code.
    """
    acc: dict = {}
    n = 0
    for lvl, lvl_codes in by_level.items():
        if not lvl_codes:
            continue
        codes = tuple(sorted(lvl_codes))
        val = _xyear("mdic_comex:exp_value", codes)
        if not val:
            continue
        wt = _xyear("mdic_comex:exp_weight", codes)
        n += len(lvl_codes)
        for y, v in val.items():
            slot = acc.setdefault(
                y, {"bruta": {"v": 0.0, "w": 0.0}, "processada": {"v": 0.0, "w": 0.0}}
            )
            slot[lvl]["v"] += v / 1e9  # US$ bi
            slot[lvl]["w"] += wt.get(y, 0.0) / 1e6  # mil t
    return acc, n


def _value_added_series_point(y: int, slot: dict) -> dict:
    """One year's processed share + price premium (price_processada / price_bruta)."""
    b, p = slot["bruta"], slot["processada"]
    total = (b["v"] + p["v"]) or 1
    price_b = (b["v"] / b["w"]) if b["w"] else 0
    price_p = (p["v"] / p["w"]) if p["w"] else 0
    return {
        "y": y,
        "brutaV": b["v"],
        "procV": p["v"],
        "procShare": p["v"] / total * 100,
        "premium": (price_p / price_b) if price_b else 0,
    }


# ── Market-nature — COMTRADE value by curated economic purpose (regime×flow) ────
# The customs procedure (customsCode) × flow (flowCode) pairs are CURATED to a
# market (consumo/processamento) by the researcher; the analysis sums COMTRADE
# value by that mapping. Real data — empty until pairs are classified.
_FLOW_LABELS = {
    "M": "Importação",
    "X": "Exportação",
    "RM": "Reimportação",
    "RX": "Reexportação",
    "DX": "Exportação nacional",
    "FM": "Importação estrangeira",
}


def _flow_market_map() -> dict:
    """{(customs_code, flow_code): market} from the log; {} when the log is absent
    (nobody classified yet) — so the matrix + analysis render before activation."""
    try:
        df = gateway.fetch_current_flow_market()
    except NotFound:
        # Log table absent (nobody classified yet) — render the matrix empty. Other
        # errors propagate instead of being masked as "not activated yet".
        return {}
    if df is None or df.empty:
        return {}
    return {(r.customs_code, r.flow_code): r.market for r in df.itertuples()}


def flow_market_worklist() -> dict:
    """The (customs procedure × flow) matrix from COMTRADE ⟕ the current market
    mapping — backs the Curadoria regime×flow editor. Cells carry the real value
    so the researcher classifies what actually matters."""
    df = gateway.fetch_comtrade_cpc_value(())
    mapping = _flow_market_map()
    customs: set = set()
    flows: set = set()
    agg: dict = {}
    if df is not None and not df.empty:
        for r in df.itertuples():
            customs.add(r.customs_code)
            flows.add(r.flow_code)
            key = (r.customs_code, r.flow_code)
            agg[key] = agg.get(key, 0.0) + float(r.value_usd or 0)
    cells = [
        {"customs_code": c, "flow_code": f, "value_usd": v, "market": mapping.get((c, f))}
        for (c, f), v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {
        "customs": sorted(customs),
        "flows": [{"code": f, "label": _FLOW_LABELS.get(f, f)} for f in sorted(flows)],
        "cells": cells,
        "classified": sum(1 for c in cells if c["market"]),
        "total": len(cells),
    }


def record_flow_market(
    customs_code: str, flow_code: str, market: str, change_id: str | None = None
) -> dict:
    """Append one (customs_code, flow_code) → market edit. Author from the IAP
    header (dev fallback per config). ``change_id`` is the optional client
    idempotency key (a retried save reusing it is a no-op). Wraps the verified
    BFF writer."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import curation

    headers = dict(request.headers) if has_request_context() else {}
    return curation.record_flow_market(
        customs_code, flow_code, market, headers, change_id=change_id
    )


def market_nature(commodity_id: str | None = None) -> dict:
    """COMTRADE trade value (US$ bi) by curated economic purpose
    (consumo/processamento) over the years, optionally scoped to ONE commodity's
    HS codes. Empty until pairs are classified."""
    mapping = _flow_market_map()
    if commodity_id:
        codes = tuple(_codes(commodity_id, "comtrade"))
        if not codes:
            # The commodity exists but has no COMTRADE (HS) codes → no global
            # trade to split. Return empty rather than silently falling through
            # to the UNSCOPED all-commodities total (an empty `codes` tuple means
            # "no filter" to fetch_comtrade_cpc_value).
            return {"years": [], "series": [], "latest": {}, "n_classified": len(mapping)}
    else:
        codes = ()
    df = gateway.fetch_comtrade_cpc_value(codes)
    markets = [m["id"] for m in ENRICH_MARKETS]
    acc = _market_nature_accumulate(df, mapping)
    years = sorted(acc)
    series = [{"y": y, **{m: acc[y].get(m, 0.0) for m in markets}} for y in years]
    return {
        "years": years,
        "series": series,
        "latest": series[-1] if series else {},
        "n_classified": len(mapping),
    }


def _market_nature_accumulate(df: pd.DataFrame | None, mapping: dict) -> dict:
    """{year: {market: US$ bi}} summed over COMTRADE rows by their curated market."""
    acc: dict = {}
    if df is None or df.empty:
        return acc
    for r in df.itertuples():
        market = mapping.get((r.customs_code, r.flow_code))
        if not market:
            continue
        slot = acc.setdefault(int(r.reference_year), {})
        slot[market] = slot.get(market, 0.0) + float(r.value_usd or 0) / 1e9
    return acc


# Economic-purpose markets the curation maps to (mirrors the frontend ENRICH_MARKETS).
ENRICH_MARKETS = [{"id": "consumo"}, {"id": "processamento"}]
