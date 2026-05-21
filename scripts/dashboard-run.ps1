# Run the Dash dashboard locally on http://localhost:8080.
# Reads GCP_PROJECT_ID (and other settings) from .env via pydantic-settings.

uv sync --extra dashboard
if (-not $?) { exit 1 }

uv run --extra dashboard python -m embrapa_commodities.dashboard.app
