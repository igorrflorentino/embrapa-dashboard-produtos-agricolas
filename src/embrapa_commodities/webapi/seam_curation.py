"""Curadoria + enrichment readers for the seam layer.

The per-code industrialization curation (bruta/processada), the value-added
analysis that splits COMEX exports by that curated level, and the market-nature
analysis that splits COMTRADE value by the curated (customs procedure × flow) →
market mapping. The READ side degrades gracefully when the gated SCD2 view /
curation log tables are not built yet: every code/cell surfaces as unclassified
instead of erroring. Writes go through the verified BFF writer (IAP author capture).

Imports only ``seam_base`` (the shared commodity toolkit) + the gateway, never
``seam`` itself, so the import graph stays acyclic. ``seam`` re-exports the public
readers/writers so ``seam.curation_worklist`` / ``seam.market_nature`` etc. keep
working unchanged.
"""

from __future__ import annotations

import pandas as pd
from google.api_core.exceptions import NotFound

from embrapa_commodities.serving import gateway
from embrapa_commodities.serving.cache import cache

from . import seam_base
from .seam_base import _LIVE_SOURCES

CUR_LEVELS = ("bruta", "processada", "misturado")


@cache.memoize()
def _code_to_commodity() -> dict:
    """{(source, code) -> commodity_id} reverse index of the crosswalk, for
    grouping the worklist by commodity."""
    idx: dict = {}
    for cid, c in seam_base.commodity_catalog().items():
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
    catalog = seam_base.commodity_catalog()
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


def value_added(commodity_id: str | None = None, uf_codes: tuple = ()) -> dict:
    """COMEX exports split by the curated industrialization level over the years.

    For each mdic_comex code currently classified bruta/processada, sum its annual
    export value (US$ bi) + weight (mil t) into that level. Real data, but empty
    until codes are classified in Curadoria. ``commodity_id`` optionally scopes to
    one crosswalk commodity. Composes existing readers — no new BFF SQL.

    Set-based: ONE value + ONE weight query per level (the reader's ``codes``
    filter is an ``IN UNNEST`` over the whole level), so the request cost stays
    flat as curators classify more codes — never 2 BigQuery round-trips per code.

    ``uf_codes`` optionally narrows the export side to one origin UF(s) — the
    bruta×processada split for a single state (cross-source per-UF scoping)."""
    by_level = _value_added_codes_by_level(commodity_id)
    acc, n = _value_added_accumulate(by_level, uf_codes)
    series = [_value_added_series_point(y, acc[y]) for y in sorted(acc)]
    return {"series": series, "n_codes": n}


def _value_added_codes_by_level(commodity_id: str | None) -> dict[str, list[str]]:
    """Group currently-classified COMEX codes into {bruta, processada} (scoped)."""
    scope = set(seam_base._codes(commodity_id, "comex")) if commodity_id else None
    by_level: dict[str, list[str]] = {"bruta": [], "processada": []}
    for (src, code), lvl in _current_code_levels().items():
        if src != "mdic_comex" or lvl not in by_level:
            continue
        if scope is not None and code not in scope:
            continue
        by_level[lvl].append(code)
    return by_level


def _value_added_accumulate(
    by_level: dict[str, list[str]], uf_codes: tuple = ()
) -> tuple[dict, int]:
    """Sum export value (US$ bi) + weight (mil t) per year per level; (acc, n_codes).

    ONE value + ONE weight query per level (the reader's ``codes`` filter is an
    ``IN UNNEST`` over the whole level), so the cost stays flat as more codes are
    classified — never 2 BigQuery round-trips per code. ``uf_codes`` narrows the
    export side to one origin UF(s) (cross-source per-UF scoping).
    """
    acc: dict = {}
    n = 0
    for lvl, lvl_codes in by_level.items():
        if not lvl_codes:
            continue
        codes = tuple(sorted(lvl_codes))
        val = seam_base._xyear("mdic_comex:exp_value", codes, uf_codes)
        if not val:
            continue
        wt = seam_base._xyear("mdic_comex:exp_weight", codes, uf_codes)
        n += len(lvl_codes)
        for y, v in val.items():
            slot = acc.setdefault(
                y, {"bruta": {"v": 0.0, "w": 0.0}, "processada": {"v": 0.0, "w": 0.0}}
            )
            slot[lvl]["v"] += v / 1e9  # US$ bi
            slot[lvl]["w"] += wt.get(y, 0.0) / 1e6  # mil t
    return acc, n


def _value_added_series_point(y: int, slot: dict) -> dict:
    """One year per level: value (US$ bi), weight (mil t), absolute unit price
    (US$/kg), the processed shares (by value and by weight), and the price premium
    (price_processada ÷ price_bruta).

    The absolute per-level prices and weights were always computed here but
    previously collapsed into the single dimensionless ``premium`` ratio; the
    "Processado vs Bruto" view needs them un-collapsed to draw the volume
    composition and the side-by-side US$/kg bars.
    """
    b, p = slot["bruta"], slot["processada"]
    total_v = (b["v"] + p["v"]) or 1
    total_w = (b["w"] + p["w"]) or 1
    # price = value(US$ bi) ÷ weight(mil t); ×1e3 → US$/kg (the COMEX exp_price unit).
    price_b = (b["v"] / b["w"] * 1e3) if b["w"] else 0
    price_p = (p["v"] / p["w"] * 1e3) if p["w"] else 0
    return {
        "y": y,
        "brutaV": b["v"],
        "procV": p["v"],
        "brutaW": b["w"],
        "procW": p["w"],
        "procShare": p["v"] / total_v * 100,
        "procShareW": p["w"] / total_w * 100,
        "priceBruta": price_b,
        "priceProc": price_p,
        "premium": (price_p / price_b) if price_b else 0,
    }


# ── Market-nature — COMTRADE value by curated economic purpose (regime×flow) ────
# The customs procedure (customsCode) × flow (flowCode) pairs are CURATED to a
# market (consumo/processamento) by the researcher; the analysis sums COMTRADE
# value by that mapping. Real data — empty until pairs are classified.
#
# pt-BR labels for ALL ten UN Comtrade flow codes (the "trade regimes" reference:
# comtradeapi.un.org/files/v1/app/reference/tradeRegimes.json). Only M/X/RM/RX are
# ingested today (config.comtrade_flows), so only those reach the worklist; the
# rest are kept here so the label is correct if the ingestion scope ever widens.
_FLOW_LABELS = {
    "M": "Importação",
    "X": "Exportação",
    "DX": "Exportação nacional",
    "FM": "Importação estrangeira",
    "MIP": "Importação para aperfeiçoamento ativo",
    "MOP": "Importação após aperfeiçoamento passivo",
    "RM": "Reimportação",
    "RX": "Reexportação",
    "XIP": "Exportação após aperfeiçoamento ativo",
    "XOP": "Exportação para aperfeiçoamento passivo",
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
        codes = tuple(seam_base._codes(commodity_id, "comtrade"))
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
