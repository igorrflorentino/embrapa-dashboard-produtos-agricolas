# Tier 2 — headless-browser visual check of the Dash dashboard.
#
# Boots the server (or targets --url), loads each key view in Chromium,
# asserts no error overlay, and writes screenshots to artifacts\.
# First run downloads Chromium (~150MB) via Playwright.
#
# Gate a deployed service:
#   scripts\dashboard-visual.ps1 --no-launch --url https://my-service.run.app

# Needs BOTH extras: `visual` for Playwright, `dashboard` so the launched
# server can import dash/plotly/bigquery-storage.
uv sync --extra dashboard --extra visual
if (-not $?) { exit 1 }

# Idempotent — no-ops once Chromium is present.
uv run --extra dashboard --extra visual python -m playwright install chromium
if (-not $?) { exit 1 }

uv run --extra dashboard --extra visual python scripts/dashboard_visual_check.py @args
exit $LASTEXITCODE
