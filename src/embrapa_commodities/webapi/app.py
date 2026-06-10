"""Flask app factory for the dashboard's REST layer + SPA host.

One Cloud Run service serves both the built React SPA (the design-system
prototype) and the ``/api`` JSON endpoints — same origin, so no CORS, and the
single IAP in front protects everything. In dev, Vite serves the SPA on :5173
and proxies ``/api`` here (:8000), so this app is API-only locally.

gunicorn entrypoint: ``embrapa_commodities.webapi.app:app``.
"""

from __future__ import annotations

import contextlib
import logging
import math
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask.json.provider import DefaultJSONProvider

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving.cache import init_cache

from .routes import api

logger = logging.getLogger(__name__)


def _json_safe(obj):
    """Replace NaN/Inf floats with None, recursively. Python's json emits a bare
    `NaN` literal (invalid JSON that JSON.parse rejects); a single NaN anywhere
    (e.g. a product with a missing name) would break the entire response. This
    guarantees every endpoint emits spec-valid JSON."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


class SafeJSONProvider(DefaultJSONProvider):
    """App JSON provider that sanitizes NaN/Inf → null before serializing."""

    ensure_ascii = False  # keep pt-BR accents readable on the wire

    def dumps(self, obj, **kwargs):
        return super().dumps(_json_safe(obj), **kwargs)


def _spa_dir() -> Path | None:
    """Where the built SPA (``frontend/dist``) lives. The prod image sets
    ``SPA_DIST_DIR``; in a dev repo it defaults to ``<repo>/frontend/dist`` if a
    build exists (else None → API-only, which is the normal dev setup)."""
    env = os.environ.get("SPA_DIST_DIR")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    candidate = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    return candidate if candidate.is_dir() else None


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json = SafeJSONProvider(app)

    # flask-caching needs GCP settings (project/dataset/TTLs). Best-effort so the
    # module still imports for lint/tests without a configured .env; at runtime
    # (Cloud Run / dev with .env) it binds and the gateway memoization works.
    with contextlib.suppress(Exception):  # pragma: no cover - depends on environment
        init_cache(app, get_settings())

    app.register_blueprint(api, url_prefix="/api")

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    spa = _spa_dir()
    if spa is not None:
        logger.info("Serving SPA from %s", spa)

        @app.get("/")
        @app.get("/<path:path>")
        def spa_catchall(path: str = ""):
            # Serve a real static asset if it exists; otherwise hand back
            # index.html so the client-side router (deep-links like ?v=&b=) loads.
            if path and (spa / path).is_file():
                return send_from_directory(spa, path)
            return send_from_directory(spa, "index.html")

    return app


app = create_app()
