# ─────────────────────────────────────────────────────────────────────────────
# React SPA + Flask REST Cloud Run SERVICE image (the Dash→React migration).
#
# Serves BOTH the built React SPA and the /api JSON endpoints from ONE origin
# (one service, one IAP, no CORS) via gunicorn → embrapa_commodities.webapi.app:app.
# Replaces the Dash image (deploy/dashboard/) at cutover — same service, same
# runtime SA, same private+IAP posture.
#
# Build context = repo ROOT (needs frontend/, pyproject.toml, uv.lock, src/, README.md):
#   Cloud Build: gcloud builds submit . --config deploy/webapi/cloudbuild.yaml \
#                  --substitutions _IMAGE=<region>-docker.pkg.dev/<proj>/<repo>/embrapa-dashboard:<tag>
#   Local:       docker build -f deploy/webapi/Dockerfile -t embrapa-webapi .
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: build the React SPA (→ /fe/dist) ────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /fe
# Lockfile-first for a cached install layer; npm ci needs package-lock.json.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: python dependency closure (webapi extra — flask + gunicorn) ──────
FROM python:3.12-slim AS pybuild
RUN pip install --no-cache-dir "uv>=0.5,<1.0"
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python3.12 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# --no-dev drops pytest/ruff; the `webapi` extra pulls flask + flask-caching +
# gunicorn (NO dash/plotly — the charts are client-side Plotly.js in the SPA).
# The seam (embrapa_commodities.webapi.seam) is UI-framework-free and resolves
# without dash installed.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra webapi

# ── Stage 3: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=pybuild --chown=appuser:appuser /app /app
# The built SPA goes where SPA_DIST_DIR points; Flask serves it for non-/api routes.
COPY --from=frontend --chown=appuser:appuser /fe/dist /app/frontend/dist

# Cloud Run injects PORT (default 8080). One gunicorn worker keeps the per-process
# flask-caching SimpleCache coherent within an instance (Cloud Run scales by
# ADDING instances, which converge via the cache TTL); threads serve the
# concurrent I/O-bound BigQuery reads. All overridable at deploy time.
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080 \
    WEB_CONCURRENCY=1 \
    GUNICORN_THREADS=8 \
    SPA_DIST_DIR=/app/frontend/dist
USER appuser
EXPOSE 8080

# Importing webapi.app:app binds flask-caching to the env settings + serves the
# SPA dir (no BigQuery I/O at import → fast cold start). Shell form so $PORT etc.
# expand; exec makes gunicorn PID 1 for correct SIGTERM on Cloud Run scale-down.
CMD exec gunicorn --bind ":$PORT" --workers "$WEB_CONCURRENCY" --threads "$GUNICORN_THREADS" \
    --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - \
    embrapa_commodities.webapi.app:app
