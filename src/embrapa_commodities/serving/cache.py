"""``flask-caching`` instance shared by the serving data-access layer.

The ``cache`` object is created unbound at import time so query functions can be
decorated with ``@cache.memoize()`` before a Flask server exists. The dashboard
calls :func:`init_cache` once, passing its Flask ``server`` (Dash's underlying
WSGI app), to bind and configure it.

Cache backend — read this before deploying to Cloud Run:

    ``SimpleCache`` is in-process and PER INSTANCE. On a multi-instance Cloud Run
    service each instance has its own cache, so a curation write that invalidates
    the classification cache on instance A does NOT clear it on instance B —
    instance B keeps serving the stale classification until its own TTL expires.

    For correct cross-instance invalidation set ``CACHE_TYPE=RedisCache`` and
    point ``CACHE_REDIS_URL`` at a shared Redis (Memorystore). The mart caches
    are TTL-only (marts change solely on the nightly dbt rebuild), so they
    tolerate per-instance caches; it is specifically the curation invalidation
    that needs the shared backend.
"""

from __future__ import annotations

from flask_caching import Cache

# Unbound until init_cache(); decorators in gateway.py reference this instance.
cache = Cache()


def init_cache(server, settings=None) -> Cache:
    """Bind and configure the cache on a Flask ``server`` from settings.

    Defaults to ``SimpleCache`` (fine for single-instance / local dev). Set
    ``CACHE_TYPE=RedisCache`` + ``CACHE_REDIS_URL`` in the environment for a
    multi-instance Cloud Run deployment (see module docstring).
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
