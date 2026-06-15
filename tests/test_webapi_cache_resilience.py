"""The webapi cache binding must be resilient to a misconfigured environment.

A fresh git worktree / sandbox starts with no ``.env``, so ``GCP_PROJECT_ID`` is
unset and ``Settings()`` raises. The old code swallowed that and left the cache
UNBOUND, which turned every ``@cache.memoize()`` data read into a cryptic
``KeyError: 'cache'`` / ``AttributeError: 'Cache' object has no attribute 'app'``
that *masked* the real "GCP_PROJECT_ID missing" cause — sending you to debug the
cache instead of your config. ``init_cache_safely`` instead binds a no-op
``NullCache`` so the cache is always present and the real error surfaces from the
data endpoints (run uncached). These tests lock that behaviour in.
"""

from __future__ import annotations

import pytest


def _patch_settings_to_fail(monkeypatch):
    """Make ``get_settings()`` raise the way a missing GCP_PROJECT_ID does.

    ``init_cache`` does a lazy ``from embrapa_commodities.config import
    get_settings`` at call time, so patching the module attribute is enough.
    """
    import embrapa_commodities.config as config_mod

    def _boom():
        raise RuntimeError("gcp_project_id Field required")  # mimics pydantic ValidationError

    monkeypatch.setattr(config_mod, "get_settings", _boom)


def test_create_app_does_not_raise_and_binds_nullcache_when_settings_missing(monkeypatch):
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import cache as cache_mod
    from embrapa_commodities.webapi import app as app_mod

    _patch_settings_to_fail(monkeypatch)

    # Must NOT raise even though Settings can't be built (the app still boots so
    # /healthz and the static SPA work, and data endpoints surface the real error).
    app = app_mod.create_app()

    # The cache is BOUND on the app — not the unbound singleton that 500s with
    # KeyError — and it is the no-op NullCache fallback.
    assert "cache" in app.extensions
    assert cache_mod.cache in app.extensions["cache"]
    assert app.extensions["cache"][cache_mod.cache].__class__.__name__ == "NullCache"


def test_memoized_read_runs_instead_of_raising_keyerror_cache(monkeypatch):
    """The regression: an unbound cache made ``@cache.memoize()`` raise
    ``KeyError: 'cache'`` BEFORE the wrapped function ran. With the NullCache
    fallback the memoized function is invoked (passthrough, never cached)."""
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_commodities.serving import cache as cache_mod
    from embrapa_commodities.webapi import app as app_mod

    _patch_settings_to_fail(monkeypatch)
    app = app_mod.create_app()

    calls = {"n": 0}

    @cache_mod.cache.memoize()
    def _double(x):
        calls["n"] += 1
        return x * 2

    with app.app_context():
        # Would raise KeyError: 'cache' on an unbound cache; now it just runs.
        assert _double(3) == 6
        assert _double(3) == 6

    # NullCache caches nothing, so the function ran on every call (no silent
    # stale-cache masking) — proves the fallback is a true passthrough.
    assert calls["n"] == 2


def test_healthz_works_even_when_settings_missing(monkeypatch):
    """A misconfigured backend must still answer /healthz and serve the shell —
    only the data endpoints depend on BigQuery config."""
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_commodities.webapi import app as app_mod

    _patch_settings_to_fail(monkeypatch)
    app = app_mod.create_app()
    app.config.update(TESTING=True)

    resp = app.test_client().get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
