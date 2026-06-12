"""``/api`` blueprint — thin REST wrappers over the serving BFF seam.

Each endpoint wraps an existing ``seam`` function and serializes (via
``serializers``) to the exact shape the prototype's ``contracts.js`` defines, so
the reused React views fetch these instead of computing synthetically. Same
Pushdown model underneath — parameterized BigQuery, memoized by flask-caching.

See ``PLANS/react_migration_contract_map.md`` §1 for the endpoint table. The
data-blocked producers (chain/lag/market-nature) have no endpoint — the views
ship honest placeholders.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving.iap import InvalidIapAssertionError

from . import seam, serializers
from .auth import current_author

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


@api.errorhandler(Exception)
def _api_error(exc):
    """Always emit parseable JSON from /api. Flask's default HTML 500 would make
    the SPA's fetch layer fail to parse and (without a client retry cap) loop;
    JSON keeps every error machine-readable. HTTP errors keep their status code."""
    if isinstance(exc, HTTPException):
        return jsonify(error=exc.description, code=exc.code), exc.code
    logger.exception("Unhandled error on %s", request.path)
    return jsonify(error="internal server error"), 500


def _authorize_curator():
    """Resolve the IAP author and enforce the curator allowlist (authorization).

    Returns ``(author, None)`` when authorized, else ``(None, (response, status))``:
    403 for a forged/invalid IAP assertion or a non-allowlisted author, 401 when
    no trustworthy identity is present at all. The effective allowlist is the
    UNION of the env var (``Settings.curation_allowed_emails``) and the
    Console-managed ``research_inputs.curators`` table; BOTH empty/absent (default)
    preserves the current "any IAP-authenticated caller may curate" behaviour.
    """
    try:
        author = current_author()
    except InvalidIapAssertionError as exc:
        return None, (jsonify(error=str(exc)), 403)
    except PermissionError as exc:  # MissingAuthorError (+ any other) → no identity
        return None, (jsonify(error=str(exc)), 401)
    allowed = set(get_settings().curation_allowed_emails_list) | seam.curator_emails()
    if allowed and author.lower() not in allowed:
        return None, (jsonify(error=f"{author} is not an authorized curator"), 403)
    return author, None


# ── catalog + provenance ──────────────────────────────────────────────────────


@api.get("/catalog")
def catalog():
    """Crosswalk commodity catalog (commodity_id → {name, pevs[], comex[], comtrade[]})."""
    return jsonify(seam.commodity_catalog())


@api.get("/source-meta")
def source_meta():
    """Provenance row for a banco (backs the page-hero meta); {} if absent.

    Shaped by ``serialize_source_meta`` into native JSON (real coverage/counters +
    the last-refresh stamp), so the frontend renders live gold_source_metadata
    instead of frozen bancos.js literals.
    """
    raw = seam.source_meta(request.args.get("banco", ""))
    return jsonify(serializers.serialize_source_meta(raw))


# ── per-banco snapshot ─────────────────────────────────────────────────────────


@api.get("/snapshot")
def snapshot():
    """Full per-banco BancoSnapshot for the chosen currency×correction. No
    year/basket/state filtering — the reused dataFilters.js narrows client-side
    (the marts are pre-aggregated/small). currency+correction pick the deflated
    value column server-side (the scientific core — see contract map §0.2)."""
    banco = request.args.get("banco", "")
    conv = {
        "currency": request.args.get("currency", "BRL"),
        "correction": request.args.get("correction", "IPCA"),
    }
    return jsonify(serializers.serialize_snapshot(seam.snapshot(banco, conv, None)))


# ── trade adapters (flow / partner / monthly) — COMEX/COMTRADE ─────────────────


@api.get("/flow")
def flow():
    """Origin→destination links for the Sankey (None when the banco lacks `flow`)."""
    banco = request.args.get("banco", "")
    return jsonify(serializers.serialize_flow(seam.flow_data(banco, None)))


@api.get("/partners")
def partners():
    """Partner ranking with export/import split."""
    banco = request.args.get("banco", "")
    return jsonify(serializers.serialize_partner(seam.partner_data(banco, None)))


@api.get("/monthly")
def monthly():
    """Monthly seasonality (COMEX only)."""
    banco = request.args.get("banco", "")
    return jsonify(serializers.serialize_monthly(seam.monthly_data(banco, None)))


# ── cross-source comparable series ─────────────────────────────────────────────


@api.get("/cross/metric-refs")
def cross_metric_refs():
    """Every (banco, metric) the cross-source picker can offer."""
    return jsonify(seam.cross_metric_refs())


@api.get("/cross/series")
def cross_series():
    """One comparable annual series for (banco, metric), in its display unit."""
    banco = request.args.get("banco", "")
    metric = request.args.get("metric", "")
    y0 = request.args.get("y0", type=int)
    y1 = request.args.get("y1", type=int)
    return jsonify(serializers.serialize_cross_series(seam.cross_series(banco, metric, y0, y1)))


# ── cross-source analytics (crosswalk-joined) ──────────────────────────────────


def _commodity() -> str | None:
    return request.args.get("commodity") or None


@api.get("/cross/export-coef")
def cross_export_coef():
    return jsonify(serializers.serialize_export_coef(seam.export_coefficient(_commodity())))


@api.get("/cross/market-share")
def cross_market_share():
    return jsonify(serializers.serialize_market_share(seam.market_share(_commodity())))


@api.get("/cross/price-spread")
def cross_price_spread():
    return jsonify(serializers.serialize_price_spread(seam.price_spread(_commodity())))


@api.get("/cross/mirror")
def cross_mirror():
    return jsonify(serializers.serialize_trade_mirror(seam.trade_mirror(_commodity())))


@api.get("/cross/value-added")
def cross_value_added():
    return jsonify(serializers.serialize_value_added(seam.value_added(_commodity())))


@api.get("/cross/market-nature")
def cross_market_nature():
    """COMTRADE value by curated economic purpose (consumo/processamento)."""
    return jsonify(serializers.serialize_market_nature(seam.market_nature(_commodity())))


# ── curation (read + write) ────────────────────────────────────────────────────


@api.get("/curation/worklist")
def curation_worklist():
    """Gold DISTINCT codes ⟕ current industrialization levels (the editor worklist)."""
    return jsonify(seam.curation_worklist())


@api.post("/curation/code-level")
def curation_code_level():
    """Append one per-code classification edit. Author captured from the IAP
    header (dev fallback per config); 401 (no identity) / 403 (invalid assertion
    or not an allowlisted curator)."""
    author, err = _authorize_curator()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    source, code, level = body.get("source"), body.get("code"), body.get("level")
    change_id = body.get("change_id")
    if not (source and code and level):
        return jsonify(error="source, code and level are required"), 400
    logger.info("curation write by %s: %s/%s → %s", author, source, code, level)
    return jsonify(seam.record_code_level(source, code, level, change_id))


@api.get("/curation/flow-worklist")
def curation_flow_worklist():
    """The (customs procedure × flow) matrix ⟕ current market (regime×flow editor)."""
    return jsonify(seam.flow_market_worklist())


@api.post("/curation/flow-market")
def curation_flow_market():
    """Append one (customs_code, flow_code) → market edit (market='' clears).
    Author from the IAP header; 401 (no identity) / 403 (invalid assertion or not
    an allowlisted curator)."""
    author, err = _authorize_curator()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    customs, flow = body.get("customs_code"), body.get("flow_code")
    market = body.get("market", "")
    change_id = body.get("change_id")
    if not (customs and flow):
        return jsonify(error="customs_code and flow_code are required"), 400
    logger.info("flow-market write by %s: %s×%s → %s", author, customs, flow, market)
    return jsonify(seam.record_flow_market(customs, flow, market, change_id))
