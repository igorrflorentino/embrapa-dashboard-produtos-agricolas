# HTTP + callback smoke test for the Dash dashboard.
#
# Boots the server on a private port (8051), drives /_health, /,
# /_dash-dependencies and a live route render against BigQuery, then tears
# the server down. Reads GCP settings from .env via pydantic-settings.
#
# Pass extra args through, e.g. to gate a deployed service:
#   scripts\dashboard-smoke.ps1 --no-launch --url https://my-service.run.app

uv sync --extra dashboard
if (-not $?) { exit 1 }

uv run --extra dashboard python scripts/dashboard_smoke.py @args
exit $LASTEXITCODE
