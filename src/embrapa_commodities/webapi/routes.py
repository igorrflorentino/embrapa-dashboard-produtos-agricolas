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

import json
import logging

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving.cache import cache
from embrapa_commodities.serving.curation import ensure_catalog_editors_table
from embrapa_commodities.serving.feedback import FeedbackValidationError, record_feedback
from embrapa_commodities.serving.iap import InvalidIapAssertionError
from embrapa_commodities.serving.research_inputs import (
    ensure_banco_metadata_table,
    ensure_curators_table,
)

from . import seam, serializers
from .auth import current_author
from .format import _CORRECTION_INFIX, _CURRENCY_SUFFIX

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


# Canonical convention vocabularies (the keys monetary_column matches on). Read
# straight from the format maps — not duplicated — so a new currency/correction
# stays validated automatically. Keys are case-sensitive exact-match (e.g.
# "IPCA"), so a typo or wrong case must 400 here instead of silently deflating
# with the BRL/IPCA fallback in monetary_column.
_ALLOWED_CURRENCIES = frozenset(_CURRENCY_SUFFIX)
_ALLOWED_CORRECTIONS = frozenset(_CORRECTION_INFIX)


def _conversion_or_400():
    """Parse + validate the currency/correction query params into a conv dict.

    Returns ``(conv, None)`` when both are valid (defaulting to BRL/IPCA when
    absent), else ``(None, (response, 400))`` with a pt-BR error naming the bad
    value. Without this, an invalid value silently falls back to BRL/IPCA inside
    monetary_column, so the user sees the wrong deflated series with no signal."""
    currency = request.args.get("currency", "BRL")
    correction = request.args.get("correction", "IPCA")
    if currency not in _ALLOWED_CURRENCIES:
        return None, (jsonify(error=f"moeda inválida: {currency!r}"), 400)
    if correction not in _ALLOWED_CORRECTIONS:
        return None, (jsonify(error=f"correção inválida: {correction!r}"), 400)
    return {"currency": currency, "correction": correction}, None


@api.errorhandler(ValueError)
def _api_value_error(exc):
    """Client-input validation errors → HTTP 400 (not 500). The serving writers raise
    ValueError with a caller-facing reason (pt-BR for the catalog writers: a bad key, an
    over-length field, an OVERLAPPING PREFIX). Surface that reason verbatim so the user
    can self-correct — a generic "check the fields" hides WHY (e.g. which prefixes clash)
    and makes the disjoint-prefix rule unusable. ValueError here is always our own
    validation; an arbitrary internal fault is an Exception → the 500 handler, never this
    path — so the message is safe to return."""
    logger.info("Invalid input on %s: %s", request.path, exc)
    return jsonify(error=str(exc) or "Dados inválidos."), 400


@api.errorhandler(Exception)
def _api_error(exc):
    """Always emit parseable JSON from /api. Flask's default HTML 500 would make
    the SPA's fetch layer fail to parse and (without a client retry cap) loop;
    JSON keeps every error machine-readable. HTTP errors keep their status code."""
    if isinstance(exc, HTTPException):
        return jsonify(error=exc.description, code=exc.code), exc.code
    logger.exception("Unhandled error on %s", request.path)
    return jsonify(error="internal server error"), 500


def _ensure_curators_table() -> None:
    """Self-heal the Console-managed curator allowlist table (best-effort).

    The allowlist read (``seam.curator_emails``) treats a missing table as "no
    allowlist configured" (open mode), so an operator following the runbook's
    documented INSERT to add the first curator would otherwise hit "table not
    found". Create it idempotently on the first authorization check — mirroring how
    the append-only log writers self-heal their own tables — so the runbook's
    "auto-creates on first use" promise actually holds. Best-effort: a transient
    BQ/permission fault must not block an otherwise-authorized write, and an empty
    table is still open mode, so swallowing the error preserves current behaviour.
    """
    try:
        ensure_curators_table()
    except Exception:  # pragma: no cover - BQ unavailable / perms; never block the write
        logger.warning("Could not ensure curators allowlist table", exc_info=True)


def _ensure_banco_metadata_table() -> None:
    """Self-heal the Console-managed banco-metadata override table (best-effort).

    The override read (``seam.banco_metadata_overrides``) treats a missing table as
    "no overrides" (registry defaults stand), so an operator following the runbook's
    documented MERGE to flip a maturity would otherwise hit "table not found". Create
    it idempotently on the first source-meta read — like the curators table — so the
    "auto-creates on first use" promise holds. Best-effort: a transient BQ/permission
    fault must never break the provenance read (an absent table is just no overrides).
    """
    try:
        ensure_banco_metadata_table()
    except Exception:  # pragma: no cover - BQ unavailable / perms; never block the read
        logger.warning("Could not ensure banco metadata override table", exc_info=True)


def _ensure_catalog_editors_table() -> None:
    """Self-heal the Console-managed per-catalog editor allowlist (best-effort).

    The allowlist read (``seam.catalog_editor_emails``) treats a missing table as
    "no allowlist → open mode", so a failure here never blocks a write — it just
    means the Console INSERT path isn't pre-created yet. Swallowed by design.
    """
    try:
        ensure_catalog_editors_table()
    except Exception:  # pragma: no cover - BQ unavailable / perms; never block the write
        logger.warning("Could not ensure catalog editors allowlist table", exc_info=True)


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
        # The message is either our own fail-closed misconfig hint ("set IAP_AUDIENCE")
        # or a google-auth verification reason. Both reach ONLY an IAP-authenticated
        # caller (no secret/token is ever echoed — the JWT itself is not), and the
        # IAP_AUDIENCE hint is a deliberately-surfaced operator deployment aid, so it is
        # returned verbatim by design (audit SEC-3: kept, info-level, no secret leak).
        return None, (jsonify(error=str(exc)), 403)
    except PermissionError as exc:  # MissingAuthorError (+ any other) → no identity
        return None, (jsonify(error=str(exc)), 401)
    # Auto-create the allowlist table on first use so the runbook's Console INSERT
    # path is real (the read below then finds an empty table → open mode).
    _ensure_curators_table()
    allowed = set(get_settings().curation_allowed_emails_list) | seam.curator_emails()
    if allowed and author.lower() not in allowed:
        return None, (jsonify(error=f"{author} is not an authorized curator"), 403)
    return author, None


def _authorize_catalog_editor(resource: str):
    """Resolve the IAP author and enforce the PER-CATALOG editor allowlist
    (``research_inputs.catalog_editors`` scoped to ``resource``) — each cadastro has
    its OWN list (the lead's decision). Same 401/403 contract as ``_authorize_curator``;
    an empty/absent allowlist preserves "any IAP-authenticated caller may edit"."""
    try:
        author = current_author()
    except InvalidIapAssertionError as exc:
        return None, (jsonify(error=str(exc)), 403)
    except PermissionError as exc:
        return None, (jsonify(error=str(exc)), 401)
    _ensure_catalog_editors_table()
    allowed = seam.catalog_editor_emails(resource)
    if allowed and author.lower() not in allowed:
        return None, (jsonify(error=f"{author} is not an authorized editor of {resource}"), 403)
    return author, None


# ── catalog + provenance ──────────────────────────────────────────────────────


@api.get("/catalog")
def catalog():
    """Crosswalk commodity catalog (commodity_id → {name, family, pevs[], comex[], comtrade[]}).

    ``family`` (PEVS physical-unit family) lets the frontend family-gate the cross
    pickers so the export-coefficient / price-spread views offer only mass commodities."""
    return jsonify(seam.commodity_catalog_with_family())


# ── Curadoria (catalog — what enters/exits the dashboard) ──────────────────────


@api.get("/catalog/entries")
def catalog_entries():
    """The current commodity catalog (latest-wins, active) — backs the admin editor.
    Optionally scoped to one banco (?banco=). Empty (not an error) before the catalog
    exists. Reading is open behind IAP; only WRITES require the editor allowlist."""
    banco = request.args.get("banco") or None
    return jsonify(serializers.serialize_catalog_worklist(seam.catalog_worklist(banco)))


@api.post("/catalog/entry")
def catalog_entry_upsert():
    """Upsert one commodity-catalog entry (the editable successor to the
    commodity_crosswalk seed). Author captured from the IAP header; 401/403 via the
    per-catalog editor allowlist. A bad key / over-length / overlapping prefix → 400."""
    author, err = _authorize_catalog_editor(seam.COMMODITY_CATALOG_RESOURCE)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if not (body.get("codigo_commodity") and body.get("banco")):
        return jsonify(error="codigo_commodity and banco are required"), 400
    logger.info(
        "catalog upsert by %s: %s/%s", author, body.get("banco"), body.get("codigo_commodity")
    )
    return jsonify(seam.record_catalog_entry(body))


@api.post("/catalog/entry/remove")
def catalog_entry_remove():
    """Remove one commodity-catalog entry — appends an active=false TOMBSTONE
    (NON-destructive: the Gold data becomes an orphan, handled by the lifecycle, never
    auto-deleted). 401/403 via the per-catalog editor allowlist."""
    author, err = _authorize_catalog_editor(seam.COMMODITY_CATALOG_RESOURCE)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if not (body.get("codigo_commodity") and body.get("banco")):
        return jsonify(error="codigo_commodity and banco are required"), 400
    logger.info(
        "catalog remove by %s: %s/%s", author, body.get("banco"), body.get("codigo_commodity")
    )
    return jsonify(seam.remove_catalog_entry(body))


@api.get("/catalog/orphans")
def catalog_orphans():
    """Orphan commodities — removed from the catalog with Gold data still lingering —
    marked Descontinuado, each with a deletion warning. Read-only detection (open behind
    IAP); the physical purge is a SEPARATE human-gated, backup-first operator step (never
    automatic). Empty before any removal."""
    return jsonify(serializers.serialize_orphan_worklist(seam.orphan_worklist()))


@api.get("/source-meta")
def source_meta():
    """Provenance row for a banco (backs the page-hero meta); {} if absent.

    Shaped by ``serialize_source_meta`` into native JSON (real coverage/counters +
    the last-refresh stamp), so the frontend renders live gold_source_metadata
    instead of frozen bancos.js literals.
    """
    _ensure_banco_metadata_table()
    raw = seam.source_meta(request.args.get("banco", ""))
    return jsonify(serializers.serialize_source_meta(raw))


# Cap the number of município codes a single /municipio-yearly request may carry.
# The legitimate IBGE municipal universe is ~5570; a small margin above it rejects a
# pathological IN-list (giant query/param payload) with a clean 400 while never
# blocking a real "all municípios in a sub-UF" selection. Mirrors _MAX_TABLE_FILTERS.
_MAX_MUNICIPIO_CODES = 5600

# Cap the number of product/UF codes any basket IN-list query param (`codes`/`states`)
# may carry. Real baskets are a few dozen products and ≤27 UFs, so this only rejects a
# pathological list; it makes every user-driven IN-list bounded symmetrically with
# _MAX_MUNICIPIO_CODES / _MAX_TABLE_FILTERS (SEC-1) — `codes` travels in the GET query
# string, so gunicorn's request-line limit already bounds it, but the explicit cap keeps
# the contract uniform regardless of transport.
_MAX_BASKET_CODES = 600


# ── raw table inspection ("Dados" perspective) ─────────────────────────────────

# Cap the number of filters a single request may apply (defense against a giant WHERE).
_MAX_TABLE_FILTERS = 5


def _parse_table_filters(raw: str | None) -> tuple:
    """Parse the JSON ``filters`` param into a tuple of ``(col, op, val)`` tuples (hashable
    for the cache key). A malformed filter → ValueError → HTTP 400. Caps the count; the
    column allowlist + value binding happen in the SQL builder."""
    if not raw:
        return ()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"filtro malformado: {exc}") from None
    if not isinstance(data, list):
        raise ValueError("filtro deve ser uma lista de {col, op, val}")
    out = []
    for f in data[:_MAX_TABLE_FILTERS]:
        if not isinstance(f, dict) or "col" not in f:
            raise ValueError("cada filtro precisa de 'col' (e opcionalmente 'op'/'val')")
        val = f.get("val")
        # Only a scalar (or null) is a valid filter value; a list/dict would bind oddly or
        # 500 in the SQL layer — reject it here as a clean 400.
        if val is not None and not isinstance(val, (str, int, float, bool)):
            raise ValueError("o valor do filtro deve ser texto, número ou booleano")
        out.append((str(f["col"]), str(f.get("op", "eq")), val))
    return tuple(out)


@api.get("/tables")
def tables():
    """Allowlisted tables a researcher may browse for a banco (the 'Dados' picker): its
    Gold table + the serving marts that feed its charts. ``[]`` for a non-live banco."""
    return jsonify(seam.inspectable_tables(request.args.get("banco", "")))


@api.get("/table")
def table():
    """One page of RAW rows for an allowlisted (banco, table) — paginated, optionally
    ordered + filtered. The (banco, table) pair + every order/filter COLUMN are validated
    server-side against the allowlist / the table's live schema (a bad one → 400); filter
    VALUES stay bound. ``limit`` is capped in the SQL builder; plain browsing uses the free
    tabledata.list path (no scan billed)."""
    page = seam.table_page(
        request.args.get("banco", ""),
        request.args.get("table", ""),
        limit=request.args.get("limit", 100, type=int),
        offset=request.args.get("offset", 0, type=int),
        order_by=request.args.get("order_by") or None,
        order_dir=request.args.get("order_dir", "asc"),
        filters=_parse_table_filters(request.args.get("filters")),
    )
    return jsonify(serializers.serialize_table_page(page))


# ── seed reference consultation (the "Referências" perspective) ────────────────


@api.get("/seeds")
def seeds():
    """Read-only seed reference tables a researcher may consult ('Referências') to
    confirm the values the pipeline relies on. Banco-agnostic (shared reference data)."""
    return jsonify(seam.seed_tables())


@api.get("/seed")
def seed():
    """One page of rows for a consultable seed reference table — the SAME grid contract
    as /api/table, but seed-scoped (the Silver reference tables) and READ-ONLY. The id +
    every order/filter COLUMN are validated server-side against the allowlist / the live
    schema; an unknown id → 400 (the gateway allowlist is the boundary)."""
    page = seam.seed_page(
        request.args.get("id", ""),
        limit=request.args.get("limit", 100, type=int),
        offset=request.args.get("offset", 0, type=int),
        order_by=request.args.get("order_by") or None,
        order_dir=request.args.get("order_dir", "asc"),
        filters=_parse_table_filters(request.args.get("filters")),
    )
    return jsonify(serializers.serialize_seed_page(page))


# ── per-banco snapshot ─────────────────────────────────────────────────────────


@api.get("/snapshot")
def snapshot():
    """Full per-banco BancoSnapshot for the chosen currency×correction. Year/basket/
    state filtering is client-side (the reused dataFilters.js narrows the small,
    pre-aggregated marts). The ONE server-side filter is ``flow`` (export/import):
    the trade snapshot is pre-aggregated OVER flow, so a direction must re-query —
    absent/``all`` sums every flow (the historical default). currency+correction pick
    the deflated value column server-side (the scientific core — see contract map
    §0.2)."""
    banco = request.args.get("banco", "")
    conv, err = _conversion_or_400()
    if err:
        return err
    flow = request.args.get("flow")
    summary = {"flow": flow} if flow else None
    return jsonify(serializers.serialize_snapshot(seam.snapshot(banco, conv, summary)))


@api.get("/product-uf")
def product_uf():
    """Real per-UF ranking for a single product (backs ViewProductProfile's
    'Onde X é produzido' bars). currency+correction pick the deflated value column
    server-side, same as /snapshot; optional startDate/endDate scope the year
    window to match the view's filter. { uf: [] } when the banco has no geo grain."""
    banco = request.args.get("banco", "")
    code = request.args.get("code", "")
    conv, err = _conversion_or_400()
    if err:
        return err
    start, end = request.args.get("startDate"), request.args.get("endDate")
    summary = {"startDate": start, "endDate": end} if (start or end) else None
    df = seam.product_uf_ranking(banco, code, conv, summary)
    return jsonify(serializers.serialize_product_uf(df))


@api.get("/geo-yearly")
def geo_yearly():
    """Basket-scoped per-(UF, year) cube (backs the geography-aware hero + map +
    series). currency+correction pick the deflated value column server-side, same as
    /snapshot; ``codes`` (comma-joined product codes; absent = all) pushes the active
    product basket down to the by-UF-yearly mart so the territorial split respects the
    selected products. The year window is left open (full history) — the client slices
    period + state; ``flow`` (export/import) re-queries server-side like /snapshot
    (absent/``all`` sums every flow). { ufYearly: [] } when the banco has no geo grain."""
    banco = request.args.get("banco", "")
    conv, err = _conversion_or_400()
    if err:
        return err
    codes = request.args.get("codes")
    flow = request.args.get("flow")
    summary: dict = {}
    if codes:
        summary["basket"] = _csv_param(codes)  # blank-strip + cap (SEC-1)
    if flow:
        summary["flow"] = flow
    df = seam.geo_yearly(banco, conv, summary or None)
    return jsonify(serializers.serialize_geo_yearly(df))


@api.get("/geo-mesh")
def geo_mesh():
    """The IBGE municipal territorial mesh (static, ~5570 rows): every município →
    UF + grande região + BOTH sub-UF divisions (classic mesorregião/microrregião,
    current região intermediária/imediata). Banco-agnostic — the SPA fetches it once
    to build the geography cascade's sub-UF + município option lists and the
    cityCode→ancestry map. { municipios: [] } if the dim isn't built."""
    return jsonify(serializers.serialize_geo_mesh(seam.geo_mesh()))


@api.post("/municipio-yearly")
def municipio_yearly():
    """Basket-scoped per-(município, year) cube — the FINEST geography grain, backing
    the live-município + sub-UF cascade (the client rolls it up to the selected level
    via /geo-mesh). **POST, not GET**: the resolved city set can be hundreds of codes,
    which would overflow a GET request line (gunicorn's default ~4 KB limit → 414), so
    ``cityCodes`` travels in the JSON body. A NON-EMPTY ``cityCodes`` is REQUIRED — the
    client only calls this once a sub-UF/município narrowing resolves to a city set, so
    an absent/empty one is a 400, and the backend never scans the full ~146k-row
    município grid. currency+correction pick the deflated value column server-side;
    ``codes`` (URL query) pushes the active product basket down. { municipioYearly: [] }
    when the banco has no município grain (COMEX/COMTRADE)."""
    banco = request.args.get("banco", "")
    conv, err = _conversion_or_400()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    raw_codes = body.get("cityCodes")
    # Must be a LIST: a bare string would otherwise char-split into bogus single-char
    # codes (e.g. "3550308" → ['3','5',...]); a non-list is a clean 400, not a silent
    # mis-parse (mirrors _parse_table_filters' type discipline).
    if not isinstance(raw_codes, list):
        return jsonify(error="cityCodes deve ser uma lista não vazia."), 400
    city = [str(c) for c in raw_codes if c]  # drop blanks; codes bind as STRING
    if not city:
        return jsonify(error="cityCodes (lista não vazia) é obrigatório."), 400
    # Cap the IN-list so a pathological request can't build a giant query/param payload
    # (the maximum_bytes_billed guard bounds the SCAN, not the parse/param overhead).
    if len(city) > _MAX_MUNICIPIO_CODES:
        return jsonify(
            error=f"cityCodes excede o limite de {_MAX_MUNICIPIO_CODES} municípios."
        ), 400
    codes = request.args.get("codes")
    summary: dict = {"cityCodes": city}
    if codes:
        summary["basket"] = _csv_param(codes)  # blank-strip + cap (SEC-1)
    df = seam.geo_municipio_yearly(banco, conv, summary)
    return jsonify(serializers.serialize_municipio_yearly(df))


@api.get("/products-by-uf")
def products_by_uf():
    """Per-product ranking WITHIN the selected UF(s) — the "Base de dados" per-UF
    product breakdown (inverse of /product-uf, which ranks UFs for ONE product).

    currency+correction pick the deflated value column server-side; codes/states/
    y0/y1 scope basket + UF + year window. ``{ products: [] }`` when no UF is
    selected or the banco has no geo grain (the view then shows a "selecione uma UF"
    hint)."""
    banco = request.args.get("banco", "")
    conv, err = _conversion_or_400()
    if err:
        return err
    df = seam.products_by_uf(banco, _filter_summary(), conv)
    return jsonify(serializers.serialize_products_by_uf(df))


@api.get("/productivity")
def productivity():
    """Área × rendimento for one crop (backs ViewProductivity, IBGE PAM only).

    `crop` picks the active crop (defaults to the first when absent). Yield (kg/ha)
    is recomputed server-side from production ÷ harvested area on the PAM mart;
    `null` when the banco lacks the `yield` capability. ``y0``/``y1`` scope the
    year window to the view's active period filter (the product basket does NOT
    apply — the crop selector is this view's own product dimension)."""
    banco = request.args.get("banco", "")
    crop = request.args.get("crop") or None
    y0, y1 = request.args.get("y0"), request.args.get("y1")
    summary = {"startDate": y0, "endDate": y1} if (y0 or y1) else None
    payload = seam.productivity(banco, crop, summary)
    return jsonify(serializers.serialize_productivity(payload))


# ── trade adapters (flow / partner / monthly) — COMEX/COMTRADE ─────────────────


def _csv_param(raw: str | None) -> list[str]:
    """Split a comma-joined query param into a list, dropping blanks.

    ``None`` (param absent) and ``''`` (cleared / all) both yield an empty list —
    i.e. no filter on that dimension. An over-long list is rejected with a 400
    (``_MAX_BASKET_CODES``) so every IN-list is bounded symmetrically (SEC-1)."""
    if not raw:
        return []
    items = [c for c in raw.split(",") if c]
    if len(items) > _MAX_BASKET_CODES:
        raise BadRequest(f"Lista de códigos excede o limite de {_MAX_BASKET_CODES}.")
    return items


def _filter_summary() -> dict | None:
    """Parse the active-filter query params into the seam's summary shape.

    The reused views pass the FilterMenu selection through the producers as URL
    params: ``codes`` (comma-joined product codes → basket), ``states``
    (comma-joined UF acronyms → states, the origin-UF filter the COMEX trade
    readers honour) and ``y0``/``y1`` (the year window). The seam reads ``basket`` +
    ``states`` + ``startDate``/``endDate``; year strings are sliced to the leading 4
    digits there, so a bare year suffices. Returns ``None`` when no filter param is
    present (the unfiltered default).
    """
    basket = _csv_param(request.args.get("codes"))
    states = _csv_param(request.args.get("states"))
    y0, y1 = request.args.get("y0"), request.args.get("y1")
    summary = {
        key: value
        for key, value in (
            ("basket", basket),
            ("states", states),
            ("startDate", y0),
            ("endDate", y1),
        )
        if value
    }
    return summary or None


@api.get("/flow")
def flow():
    """Origin→destination links for the Sankey (None when the banco lacks `flow`).

    ``codes``/``states``/``y0``/``y1`` scope the basket + origin-UF + year window to
    match the view's active filters (the seam threads them into the gateway flow
    reader; ``states`` narrows the COMEX origin only — COMTRADE's origin is a
    reporter country, so the frontend surfaces it as not-applicable there)."""
    banco = request.args.get("banco", "")
    return jsonify(serializers.serialize_flow(seam.flow_data(banco, _filter_summary())))


_ALLOWED_PARTNER_METRICS = frozenset({"value", "weight", "price"})


@api.get("/partners")
def partners():
    """Partner ranking with export/import split (basket + origin-UF + year window
    via ``codes``/``states``/``y0``/``y1``; ``states`` applies to COMEX only).

    ``metric`` ∈ {value, weight, price} (default ``value``) ranks by Capital /
    Volume / Preço médio server-side, so the top-N is by the chosen dimension."""
    banco = request.args.get("banco", "")
    metric = request.args.get("metric", "value")
    if metric not in _ALLOWED_PARTNER_METRICS:
        return jsonify(error=f"métrica inválida: {metric!r}"), 400
    return jsonify(
        serializers.serialize_partner(seam.partner_data(banco, _filter_summary(), rank_by=metric))
    )


@api.get("/monthly")
def monthly():
    """Monthly seasonality, COMEX only (basket + year window via
    ``codes``/``y0``/``y1``). The seasonality mart collapses UF away, so the UF
    (``states``) filter does not apply here — the frontend surfaces that honestly."""
    banco = request.args.get("banco", "")
    return jsonify(serializers.serialize_monthly(seam.monthly_data(banco, _filter_summary())))


# ── cross-source comparable series ─────────────────────────────────────────────


@api.get("/cross/metric-refs")
def cross_metric_refs():
    """Every (banco, metric) the cross-source picker can offer."""
    return jsonify(seam.cross_metric_refs())


def _uf_codes() -> tuple[str, ...]:
    """Origin-UF acronyms from the ``states`` param (cross-source per-UF scoping).

    Empty = national (no UF filter). Only the UF-capable sides (IBGE PEVS, MDIC
    COMEX) honour it; COMTRADE-origin series ignore it (the view notes that)."""
    return tuple(_csv_param(request.args.get("states")))


@api.get("/cross/series")
def cross_series():
    """One comparable annual series for (banco, metric), in its display unit.
    ``states`` optionally narrows to origin UF(s) for the UF-capable bancos."""
    banco = request.args.get("banco", "")
    metric = request.args.get("metric", "")
    y0 = request.args.get("y0", type=int)
    y1 = request.args.get("y1", type=int)
    return jsonify(
        serializers.serialize_cross_series(seam.cross_series(banco, metric, y0, y1, _uf_codes()))
    )


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
    """``states`` optionally narrows the porteira-vs-FOB spread to one origin UF(s)."""
    return jsonify(serializers.serialize_price_spread(seam.price_spread(_commodity(), _uf_codes())))


@api.get("/cross/mirror")
def cross_mirror():
    return jsonify(serializers.serialize_trade_mirror(seam.trade_mirror(_commodity())))


# ─── Feedback ("Reportar problema") ─────────────────────────────────────────────
def _peek_author():
    """Best-effort author for the per-author rate-limit key; None when no trustworthy
    identity is present (record_feedback then raises the real 401/403)."""
    try:
        return current_author()
    except Exception:  # fall through; record_feedback raises the real 401/403
        return None


@api.post("/feedback")
def feedback_submit():
    """Append one user feedback report (bug/dúvida/sugestão) and best-effort open a
    GitHub issue. ANY IAP-authenticated user may submit (no curator allowlist); the
    author is captured server-side from IAP — there is no client-supplied identity.
    A short per-author cooldown debounces double-clicks/abuse (SEC-2). 400 on empty/
    over-length message or bad category; 401/403 on no/forged identity; 429 on cooldown."""
    body = request.get_json(silent=True) or {}
    cooldown = get_settings().feedback_cooldown_seconds
    author = _peek_author()
    rl_key = f"fb:cooldown:{author.lower()}" if author else None
    if rl_key and cooldown and cache.get(rl_key):
        return jsonify(error="Aguarde alguns segundos antes de enviar outro feedback."), 429
    try:
        result = record_feedback(
            category=body.get("category", "bug"),
            message=body.get("message", ""),
            headers=request.headers,
            url=body.get("url"),
            view=body.get("view"),
            banco=body.get("banco"),
            app_version=body.get("app_version"),
            browser_info=body.get("browser_info"),
            author=author,
        )
    except FeedbackValidationError as exc:
        return jsonify(error=str(exc)), 400
    except InvalidIapAssertionError as exc:
        return jsonify(error=str(exc)), 403
    except PermissionError as exc:  # MissingAuthorError → no trustworthy identity
        return jsonify(error=str(exc)), 401
    if rl_key and cooldown:
        cache.set(rl_key, 1, timeout=cooldown)
    return jsonify(result)


# ─── FROZEN FEATURE: Curadoria / enrichment endpoints ───────────────────────────
# The curated value-added + market-nature readers (below) and the /curation/* editor
# read/write routes are postponed to the "Versão Futura" roadmap phase (leadership
# decision, 2026-06). Their UI entry points are hidden (views.js + AppShell.jsx), so
# the app runs fully decoupled; the routes stay registered + tested and degrade
# gracefully (empty results when `enable_curation` is unbuilt). Kept as the scaffold
# for the real future implementation — do not delete.
@api.get("/cross/value-added")
def cross_value_added():
    """``states`` optionally narrows the bruta×processada split to one origin UF(s)."""
    return jsonify(serializers.serialize_value_added(seam.value_added(_commodity(), _uf_codes())))


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
