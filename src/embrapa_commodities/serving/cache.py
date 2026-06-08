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
    return cache
