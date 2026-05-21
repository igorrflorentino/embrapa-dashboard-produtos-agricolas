# syntax=docker/dockerfile:1.7
# Build context: repo root (so the Dockerfile can see pyproject.toml + src/).
# `gcloud run deploy --source .` honors this when you point it at the repo root.

# ───── builder stage ─────
FROM python:3.12.11-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# Lock + manifest first → maximum layer cache reuse.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Install only runtime deps + the dashboard extra. No dev tooling in the image.
RUN uv sync --frozen --no-dev --extra dashboard

# ───── runtime stage ─────
FROM python:3.12.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LOG_LEVEL=INFO

# Non-root user (Cloud Run honors USER directive).
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder /app /app
RUN chown -R app:app /app

USER app
EXPOSE 8080

# Gunicorn: 2 workers × 4 threads is enough for a small in-memory dashboard.
# `--preload` shares the BigQuery snapshot across workers via fork-after-import.
CMD exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    embrapa_commodities.dashboard.app:server
