"""SPA-host wiring in the webapi app factory.

One Cloud Run service serves both the built React SPA and the ``/api`` JSON
endpoints. The SPA half is driven by ``_spa_dir()`` (which dir to serve) and the
``spa_catchall`` route (serve a real asset, else fall back to ``index.html`` so
the client-side router handles deep links). These tests pin that behaviour using
a temp dist dir via ``SPA_DIST_DIR`` — deterministic regardless of whether a real
``frontend/dist`` build exists in the checkout.
"""

from __future__ import annotations

import pytest

# Importing the webapi app pulls flask at module load (app.py does
# ``from flask import ...``; serving.cache uses flask-caching), which live only
# in the ``webapi``/``dev`` extras — so the WHOLE module skips (not errors) on a
# core-only install, matching the rest of tests/test_webapi_*.
pytest.importorskip("flask")
pytest.importorskip("flask_caching")


def _make_dist(tmp_path):
    """A minimal built-SPA dir: index.html + one hashed asset."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')", encoding="utf-8")
    return dist


def test_spa_dir_env_pointing_at_existing_dir_is_returned(monkeypatch, tmp_path):
    """SPA_DIST_DIR set to a real directory → that Path (the prod-image case)."""
    from embrapa_commodities.webapi import app as app_mod

    dist = _make_dist(tmp_path)
    monkeypatch.setenv("SPA_DIST_DIR", str(dist))

    assert app_mod._spa_dir() == dist


def test_spa_dir_env_pointing_at_missing_dir_is_none(monkeypatch, tmp_path):
    """SPA_DIST_DIR set but the dir doesn't exist → None (don't serve a ghost)."""
    from embrapa_commodities.webapi import app as app_mod

    monkeypatch.setenv("SPA_DIST_DIR", str(tmp_path / "does-not-exist"))

    assert app_mod._spa_dir() is None


def test_app_serves_index_static_and_deeplink_fallback(monkeypatch, tmp_path):
    """With a dist present the app serves real assets, and any unknown path falls
    back to index.html so the SPA router can resolve deep links (?v=&b=)."""
    from embrapa_commodities.webapi import app as app_mod

    dist = _make_dist(tmp_path)
    monkeypatch.setenv("SPA_DIST_DIR", str(dist))

    app = app_mod.create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    # Root → index.html (the SPA shell).
    root = client.get("/")
    assert root.status_code == 200
    assert b"<title>SPA</title>" in root.data
    # index.html must be served no-cache so a ?v=<version> css bump / new js hash
    # always reaches the browser instead of a stale cached shell pinning the old ones.
    assert "no-cache" in root.headers.get("Cache-Control", "")

    # A real hashed asset is served from disk, not the index fallback.
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert b"console.log('app')" in asset.data

    # An unknown client-side route (no file on disk) → index.html, status 200,
    # so the React router loads instead of a 404 — and also no-cache.
    deeplink = client.get("/produto/123")
    assert deeplink.status_code == 200
    assert b"<title>SPA</title>" in deeplink.data
    assert "no-cache" in deeplink.headers.get("Cache-Control", "")


def test_unknown_api_path_is_json_404_not_spa_html(monkeypatch, tmp_path):
    """Even with the SPA mounted, an unknown /api path must return machine-readable
    JSON 404 — never index.html with HTTP 200 (which would burn the fetch layer's
    retry budget on a parse error)."""
    from embrapa_commodities.webapi import app as app_mod

    dist = _make_dist(tmp_path)
    monkeypatch.setenv("SPA_DIST_DIR", str(dist))

    app = app_mod.create_app()
    app.config.update(TESTING=True)

    resp = app.test_client().get("/api/nao-existe")
    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()["code"] == 404


def test_json_safe_maps_pandas_na_and_nat_to_null():
    """pandas missing-value singletons from a nullable BigQuery column (the raw-table
    /api/table inspection path is the first endpoint to surface them) must serialize to
    JSON null: pd.NA crashes the json encoder (a 500), and pd.NaT.isoformat() would leak
    the literal string "NaT" through the datetime branch. Floats stay NaN→null as before."""
    import pandas as pd

    from embrapa_commodities.webapi import app as app_mod

    assert app_mod._json_safe(pd.NA) is None
    assert app_mod._json_safe(pd.NaT) is None
    # nested inside the {columns, rows:[[...]]} shape serialize_table_page emits
    out = app_mod._json_safe({"rows": [[1, pd.NA, pd.NaT, float("nan")]], "ok": True})
    assert out == {"rows": [[1, None, None, None]], "ok": True}


def test_json_safe_coerces_decimal_to_float():
    """A BigQuery NUMERIC/BIGNUMERIC column materializes as decimal.Decimal in
    df.values.tolist() (the raw-table inspector). Decimal is not a float subclass, so
    the stdlib encoder would 500 on it — coerce to float, and a NUMERIC NaN → null (JSON-1)."""
    import decimal

    from embrapa_commodities.webapi import app as app_mod

    assert app_mod._json_safe(decimal.Decimal("3.14")) == 3.14
    assert app_mod._json_safe(decimal.Decimal("0")) == 0.0
    assert app_mod._json_safe(decimal.Decimal("NaN")) is None  # non-finite → null
