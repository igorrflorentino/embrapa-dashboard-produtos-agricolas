"""``flask-caching`` instance shared by the serving data-access layer.

The ``cache`` object is created unbound at import time so query functions can be
decorated with ``@cache.memoize()`` before a Flask server exists. The webapi app
factory calls :func:`init_cache` once, passing its Flask app, to bind and
configure it.

Cache backend — multi-instance Cloud Run on ``SimpleCache`` (the default) works,
for free:

    ``SimpleCache`` is in-process and PER INSTANCE. The mart caches tolerate that
    trivially (marts change only on the nightly dbt rebuild, so every instance
    converges within the TTL). The one caveat is the curation classification
    cache — a write on instance A can't invalidate B's copy — and it is handled
    NOT by Redis but by a SHORT TTL (``CACHE_CLASSIFICATION_TIMEOUT``, default
    30s, applied in ``gateway.py``): the writing instance is invalidated
    instantly, others converge within that window. Eventual consistency ≤30s is
    fine for manual research curation, so the dashboard scales to N instances at
    zero cost.

    ``CACHE_TYPE=RedisCache`` + ``CACHE_REDIS_URL`` (Memorystore) is OPTIONAL —
    reach for it only if you ever need *instant* (sub-second) cross-instance
    classification consistency under high traffic, which this workload does not.

Two ``SimpleCache`` internals are knowingly accepted (NOT worked around — they are
flask-caching/Werkzeug behaviour, not our bug):

  * Eviction at the 500-entry threshold (Werkzeug default) prunes expired-then-
    oldest entries NON-atomically. Under concurrent writes an entry can be
    evicted slightly early or a stale one linger briefly. Most of the keyspace is
    tiny (a handful of mart shapes + one classification read), BUT the raw-table
    inspection ("Dados") readers memoize on arbitrary user-supplied (filter-value,
    offset) tuples, so an authenticated caller CAN generate many distinct keys —
    the 500-entry cap (each entry <= RAW_TABLE_MAX_LIMIT rows) is therefore the
    LOAD-BEARING memory bound now, not a never-hit theoretical one. It is still not
    an exhaustion vector (total memory stays bounded); an early eviction is just a
    cache miss → a correct re-query. (Relevant for a future Redis migration.)
  * Invalidation via ``delete_memoized`` bumps a version sentinel instead of
    deleting entries, so orphaned values persist until their TTL (documented at
    the call site in ``serving.attribute_engineering``). Bounded, eventual (<= TTL) — fine here.
"""

from __future__ import annotations

import logging

from flask_caching import Cache

logger = logging.getLogger(__name__)

# Unbound until init_cache(); decorators in gateway.py reference this instance.
cache = Cache()


def init_cache(server, settings=None) -> Cache:
    """Bind and configure the cache on a Flask ``server`` from settings.

    Defaults to ``SimpleCache``, which scales to N Cloud Run instances for free
    (mart TTLs + a short classification TTL — see module docstring). Set
    ``CACHE_TYPE=RedisCache`` + ``CACHE_REDIS_URL`` only for *instant*
    cross-instance classification consistency (optional, not required).

    Also binds the *authoritative* curation-read TTL: the classification fetch is
    decorated with a static default before Settings exists, so here — where we have
    Settings — we set its writable ``cache_timeout`` attribute (which flask-caching
    re-reads per call) to ``cache_classification_timeout``. That makes the config
    field the single source of truth instead of a separately-read env var.
    """
    from embrapa_commodities.config import get_settings

    cfg = settings or get_settings()
    config = {
        "CACHE_TYPE": cfg.cache_type,
        "CACHE_DEFAULT_TIMEOUT": cfg.cache_default_timeout,
    }
    if cfg.cache_redis_url:
        config["CACHE_REDIS_URL"] = cfg.cache_redis_url
    cache.init_app(server, config=config)
    _bind_classification_ttl(cfg.cache_classification_timeout)
    return cache


def init_cache_safely(server) -> Cache:
    """Bind the cache, falling back to a no-op ``NullCache`` if settings/binding fail.

    A real bind needs GCP settings (project / dataset / TTLs from ``Settings``).
    In a MISCONFIGURED environment — most commonly a fresh git worktree or sandbox
    with no ``.env`` (so ``GCP_PROJECT_ID`` is unset and ``Settings()`` raises) — we
    still bind a ``NullCache`` so the cache is PRESENT on the app.

    Why this matters: without a bound cache, every ``@cache.memoize()`` read in
    ``gateway`` later explodes with a cryptic ``KeyError: 'cache'`` /
    ``AttributeError: 'Cache' object has no attribute 'app'`` that *masks* the real
    cause and sends you debugging the cache instead of your config. With a bound
    ``NullCache`` the memoized reads simply run UNCACHED and surface the actual
    underlying error (e.g. ``gcp_project_id Field required``) directly — far more
    debuggable when running locally under the preview. Returns the bound cache
    either way; callers need not handle exceptions.
    """
    try:
        return init_cache(server)
    except Exception:
        logger.error(
            "init_cache failed — CACHING IS DISABLED: binding a no-op NullCache so "
            "the app still boots, but gateway memoization is OFF (the mart, "
            "curator-allowlist, and classification TTLs do nothing) and the "
            "curation-cache invalidation guarantees are VOID until this is fixed — "
            "every data endpoint runs UNCACHED and re-queries BigQuery. In prod this "
            "must be treated as a misconfiguration, not a steady state. Most often it "
            "means no .env / GCP_PROJECT_ID is configured, e.g. a fresh worktree: "
            "copy a working .env into the repo root or run "
            "`uv run python scripts/setup_dev_env.py`.",
            exc_info=True,
        )
        cache.init_app(server, config={"CACHE_TYPE": "NullCache"})
        return cache


def _bind_classification_ttl(timeout: int) -> None:
    """Point the memoized curation reads at the Settings-derived TTL.

    Imported lazily (gateway imports this module) to dodge a circular import.
    flask-caching reads ``decorated_fn.cache_timeout`` on every call, so updating
    it here overrides the decoration-time default with the authoritative value.
    All the curation reads (per-code, flow-market, the curator allowlist AND the
    banco-maturity metadata) must use the short classification TTL — that short
    window is what bounds cross-instance staleness on per-process SimpleCache. The
    curator allowlist gates POST /api/curation/* authorization, so its read must also
    honor the configured value: an operator who lowers CACHE_CLASSIFICATION_TIMEOUT to
    revoke a removed curator faster would otherwise see no effect (the allowlist would
    stay pinned at the decoration-time default). fetch_banco_metadata is the same
    class — its docstring promises a Console maturity flip reflects within the
    classification window — so it must be rebound too. Rebind all four.
    """
    from embrapa_commodities.serving import gateway

    gateway.fetch_current_code_industrialization.cache_timeout = timeout
    gateway.fetch_current_flow_market.cache_timeout = timeout
    gateway.fetch_curators.cache_timeout = timeout
    gateway.fetch_banco_metadata.cache_timeout = timeout
