# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Cloud Run SERVICE image — serves the Dash app over HTTP via gunicorn.
#
# This is the long-lived HTTP Service (the Claude Design System dashboard), NOT
# the batch ingestion Job (that lives under deploy/ingestion/, runs the CLI and
# exits). Build context = repo ROOT (needs pyproject.toml, uv.lock, src/, README.md):
#   Cloud Build: gcloud builds submit --config deploy/dashboard/cloudbuild.yaml \
#                  --substitutions _IMAGE=<region>-docker.pkg.dev/<proj>/<repo>/embrapa-dashboard:<tag> .
#   Local:       docker build -f deploy/dashboard/Dockerfile -t embrapa-dashboard .
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS build

RUN pip install --no-cache-dir "uv>=0.5,<1.0"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python3.12 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency closure first (cached layer), then the package. --no-dev drops
# pytest/ruff; the `dashboard` extra pulls dash + plotly + flask-caching +
# gunicorn. Installed EDITABLE (no --no-editable): the package ships non-Python
# data files (assets/: CSS, fonts, logos) that Dash serves at runtime, and an
# editable install guarantees they resolve from the in-image source tree.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra dashboard

# ── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app

# Put the project venv on PATH so `gunicorn` resolves directly. Cloud Run injects
# PORT (default 8080). One gunicorn worker keeps the per-process flask-caching
# SimpleCache coherent within an instance (Cloud Run scales by ADDING instances,
# which converge via the cache TTL — see serving/cache.py); threads serve the
# concurrent, I/O-bound BigQuery reads. Both are overridable at deploy time.
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080 \
    WEB_CONCURRENCY=1 \
    GUNICORN_THREADS=8
USER appuser
EXPOSE 8080

# Serve the Dash app's Flask `server` object. Importing app:server binds
# flask-caching to the environment's settings (no BigQuery I/O at import, so cold
# start stays fast). Shell form so $PORT/$WEB_CONCURRENCY expand; `exec` makes
# gunicorn PID 1 for correct SIGTERM handling on Cloud Run scale-down.
CMD exec gunicorn --bind ":$PORT" --workers "$WEB_CONCURRENCY" --threads "$GUNICORN_THREADS" \
    --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - \
    embrapa_commodities.dashboard.app:server
