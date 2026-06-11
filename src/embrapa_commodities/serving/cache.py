"""``flask-caching`` instance shared by the serving data-access layer.

The ``cache`` object is created unbound at import time so query functions can be
decorated with ``@cache.memoize()`` before a Flask server exists. The dashboard
calls :func:`init_cache` once, passing its Flask ``server`` (Dash's underlying
WSGI app), to bind and configure it.

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
    evicted slightly early or a stale one linger briefly. The serving keyspace is
    tiny (a handful of mart shapes + one classification read), so the cap is never
    realistically hit; if it were, an early eviction is just a cache miss → a
    correct re-query. No correctness impact, only a marginal extra BigQuery read.
  * Invalidation via ``delete_memoized`` bumps a version sentinel instead of
    deleting entries, so orphaned values persist until their TTL (documented at
    the call site in ``serving.curation``). Bounded, eventual (<= TTL) — fine here.
"""

from __future__ import annotations

from flask_caching import Cache

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


def _bind_classification_ttl(timeout: int) -> None:
    """Point the memoized curation reads at the Settings-derived TTL.

    Imported lazily (gateway imports this module) to dodge a circular import.
    flask-caching reads ``decorated_fn.cache_timeout`` on every call, so updating
    it here overrides the decoration-time default with the authoritative value.
    ALL THREE curation reads (commodity-level, per-code, and flow-market) must use
    the short classification TTL — that short window is what bounds cross-instance
    staleness on per-process SimpleCache — so rebind all three, not just the first.
    """
    from embrapa_commodities.serving import gateway

    gateway.fetch_current_classifications.cache_timeout = timeout
    gateway.fetch_current_code_industrialization.cache_timeout = timeout
    gateway.fetch_current_flow_market.cache_timeout = timeout
