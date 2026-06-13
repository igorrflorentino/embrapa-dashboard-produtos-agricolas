# ─────────────────────────────────────────────────────────────────────────────
# Ingestion Cloud Run JOB image — runs `embrapa ingest all` to completion.
#
# This is the BATCH ingestion job, NOT the dashboard Service image (that one is
# deploy/webapi/Dockerfile — the React SPA + Flask REST service). It has no HTTP
# server; it runs the CLI and exits. Build context = repo ROOT (needs pyproject.toml, uv.lock,
# src/, README.md):
#   Cloud Build: gcloud builds submit --config deploy/ingestion/cloudbuild.yaml \
#                  --substitutions _IMAGE=<region>-docker.pkg.dev/<proj>/<repo>/embrapa-ingest-all:<tag> .
#   Local:       docker build -f deploy/ingestion/Dockerfile -t embrapa-ingest-all .
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS build

RUN pip install --no-cache-dir "uv>=0.5,<1.0"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=python3.12 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency closure first (cached layer), then the package. --no-dev drops
# pytest/ruff; the `serving` extra is intentionally absent — the job only needs
# the ingestion CLI, so the image stays lean (no Flask, no flask-caching).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app

# Put the project venv on PATH so the `embrapa` console script resolves directly.
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# Batch entrypoint: run the full Bronze ingestion, then exit (a Job, not a
# Service). COMTRADE is excluded from `all` (key-gated), so no secret is needed.
# Override CMD at deploy time to ingest a single source, e.g. ["ibge"].
ENTRYPOINT ["embrapa", "ingest"]
CMD ["all"]
