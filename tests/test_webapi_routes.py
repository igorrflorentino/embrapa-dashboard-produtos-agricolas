"""HTTP-layer tests for the ``/api`` blueprint via Flask's ``test_client``.

These sit beneath the pure ``test_webapi_seam`` / ``test_webapi_serializers``
unit tests and exercise the request → auth → JSON contract that nothing else
guards: the curation-write authentication (401) / authorization (403), input
validation (400), the JSON error handler, and the curator allowlist. No
BigQuery — Settings is stubbed and seam functions are monkeypatched.
"""

from __future__ import annotations

import pytest


def _client(monkeypatch, **settings_over):
    pytest.importorskip("flask")
    pytest.importorskip("flask_caching")
    from embrapa_commodities.config import Settings
    from embrapa_commodities.webapi import app as app_mod
    from embrapa_commodities.webapi import auth, routes

    base = {
        "gcp_project_id": "test-project",
        "curation_dev_author": None,
        "iap_audience": None,
        "curation_allowed_emails": "",
    }
    base.update(settings_over)
    cfg = Settings(**base)
    # Auth + allowlist read get_settings from their own module namespaces.
    monkeypatch.setattr(auth, "get_settings", lambda: cfg)
    monkeypatch.setattr(routes, "get_settings", lambda: cfg)
    app = app_mod.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_healthz_ok(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_curation_post_without_identity_is_401(monkeypatch):
    """No IAP header + no dev fallback → MissingAuthorError → 401 JSON (never writes)."""
    client = _client(monkeypatch)  # curation_dev_author=None, iap_audience=None
    resp = client.post(
        "/api/curation/code-level", json={"source": "x", "code": "1", "level": "bruta"}
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_curation_post_missing_fields_is_400(monkeypatch):
    """Authenticated (dev fallback) but an incomplete body → 400 before any write."""
    client = _client(monkeypatch, curation_dev_author="dev@embrapa.br")
    resp = client.post("/api/curation/code-level", json={"source": "x"})  # no code/level
    assert resp.status_code == 400


def test_curation_post_not_in_allowlist_is_403(monkeypatch):
    """A real identity that is NOT on the curator allowlist → 403 (authorization)."""
    client = _client(
        monkeypatch,
        curation_dev_author="intruder@embrapa.br",
        curation_allowed_emails="curator@embrapa.br",
    )
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 403


def test_curation_post_invalid_iap_assertion_is_403(monkeypatch):
    """An audience is configured but no signed JWT is present → InvalidIapAssertion → 403."""
    client = _client(monkeypatch, iap_audience="/projects/1/global/backendServices/2")
    resp = client.post(
        "/api/curation/code-level",
        json={"source": "x", "code": "1", "level": "bruta"},
    )
    assert resp.status_code == 403


def test_api_error_handler_returns_json_not_html(monkeypatch):
    """An unhandled error in a read endpoint returns parseable JSON (so the SPA's
    fetch layer doesn't choke on Flask's default HTML 500 and retry-loop)."""
    client = _client(monkeypatch)
    from embrapa_commodities.webapi import seam

    def boom():
        raise RuntimeError("BigQuery exploded")

    monkeypatch.setattr(seam, "commodity_catalog", boom)
    resp = client.get("/api/catalog")
    assert resp.status_code == 500
    assert resp.content_type.startswith("application/json")
    assert resp.get_json()["error"] == "internal server error"
