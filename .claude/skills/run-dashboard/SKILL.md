---
name: run-dashboard
description: >-
  Run, launch, build, serve, smoke-test, and screenshot the Embrapa commodities
  Dash dashboard (the Plotly Dash web app in src/embrapa_commodities/dashboard).
  Use when asked to run / start / serve the dashboard, verify it renders, drive
  it, screenshot it, or gate a deploy. Driven by scripts/dashboard_smoke.py
  (HTTP + Dash-callback, no browser) and scripts/dashboard_visual_check.py
  (headless Chromium screenshots).
---

# Run the Embrapa commodities dashboard

A Plotly **Dash** web app (`src/embrapa_commodities/dashboard/`, Flask WSGI app
exposed as `…app:server`). It renders **client-side** and lazily runs
`SELECT * FROM <gold table>` against **BigQuery** on the first page view — there
is no offline/sample mode, so a real run needs `.env` + ADC + a populated Gold
table.

Because rendering is client-side, `curl /` only proves the shell loads. To
actually exercise a page (and BigQuery) you drive it through one of two
committed harnesses:

- **`scripts/dashboard_smoke.py`** — stdlib only. Boots the server, hits
  `/_health`, `/`, `/_dash-dependencies`, then POSTs the route callback to
  render a page (forces the live BigQuery load). Fast, no browser. This is the
  primary agent path and the deploy gate.
- **`scripts/dashboard_visual_check.py`** — launches headless Chromium
  (Playwright), loads each key view, asserts no error overlay, and writes a
  screenshot per view to `artifacts/`.

> Paths are relative to the repo root. Verified on **Windows (PowerShell + uv)**;
> `make` targets (`dashboard-smoke`, `dashboard-visual`, `dashboard-run`) are the
> Unix/CI equivalents but were not run here.

## Prerequisites

- `uv` (Python 3.12 pinned via `pyenv local 3.12.11` / `uv sync`).
- `.env` with `GCP_PROJECT_ID`, `BQ_GOLD_DATASET`, `BQ_LOCATION` (copy from
  `.env.example`).
- Application Default Credentials: `gcloud auth application-default login`.
- A populated Gold table (`make dbt-build-prod`, or `gold_commodity_matrix`
  already exists in the configured dataset/location).

## Build / setup

```powershell
uv sync --extra dashboard
```

For the visual checker, sync **both** extras and install the browser once
(~180 MB):

```powershell
uv sync --extra dashboard --extra visual
uv run --extra dashboard --extra visual python -m playwright install chromium
```

## Run — agent path (drive it)

**Tier 1 — HTTP/callback smoke (fast, no browser):**

```powershell
uv run --extra dashboard python scripts/dashboard_smoke.py
```

Boots the server on a private port (8051), runs four checks, tears it down.
All-pass prints `All smoke checks passed.` and exits 0. The fourth check
("POST route render /ibge-pevs/visao-geral") is the one that forces the live
BigQuery snapshot; a green here means the data path works end-to-end.

Gate an already-running or deployed instance instead of launching one:

```powershell
uv run --extra dashboard python scripts/dashboard_smoke.py --no-launch --url http://127.0.0.1:8080
```

**Tier 2 — visual / screenshots:**

```powershell
uv run --extra dashboard --extra visual python scripts/dashboard_visual_check.py
```

Captures `artifacts/overview.png`, `product.png`, `geography.png`, `tabela.png`.
**Open the screenshots and look** — a blank frame or the error overlay means it
did not really render, even if the run "passed."

**PowerShell wrappers** do the `uv sync` (+ `playwright install`) for you and
pass extra args through:

```powershell
.\scripts\dashboard-smoke.ps1
.\scripts\dashboard-visual.ps1
```

## Run — human path

```powershell
uv run --extra dashboard python -m embrapa_commodities.dashboard.app
```

Serves `http://localhost:8080` (override with `$env:PORT`). Open
`http://localhost:8080/ibge-pevs/visao-geral`. Healthcheck: `GET /_health` →
`{"status":"ok"}`. Ctrl-C to stop. Headless, this just sits there — use the
smoke for verification.

## Gotchas (the non-obvious ones)

- **Launch via the venv interpreter, not `uv run`.** The driver spawns
  `.venv\Scripts\python.exe -m …app` directly (see `_server_python` in
  `scripts/dashboard_smoke.py`). Going through `uv run` leaves an
  **unreapable python grandchild** that keeps holding the port and the venv
  files after `terminate()` — which then makes a later `uv sync` fail with
  "Access denied" (see Troubleshooting).
- **Visual needs BOTH extras.** `uv ... --extra visual` *alone* reconciles the
  env to base+visual and **removes dash/plotly**, so the server won't boot
  (`ImportError` on `dash`/`flask`). Always `--extra dashboard --extra visual`.
- **Health is `/_health`, not `/healthz`.** Google Frontend reserves
  `/healthz` on Cloud Run, so the app exposes its check at `/_health`.
- **BigQuery errors don't 500 the page.** Layout exceptions are caught into a
  full-screen error overlay and the HTTP response is still 200. The smoke
  detects this via the `global-error` store value; the visual via
  `#error-overlay.visible`.
- **Driving Dash callbacks:** the smoke builds the
  `POST /_dash-update-component` body from `/_dash-dependencies` — it finds the
  route callback (the one keyed on `url.pathname`) and fires it with
  `/ibge-pevs/visao-geral`. `/` redirects to that canonical path client-side.

## Troubleshooting

- **`uv sync` → "failed to remove directory … Acesso negado / Access denied"`**
  on a `*.dist-info`: a dashboard server is still running and holding venv
  files. Kill it, then retry:
  ```powershell
  Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'dashboard\.app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```
  If a package ends up half-removed (`ImportError: cannot import name X
  (unknown location)` — happened to `blinker`), repair it:
  ```powershell
  uv sync --extra dashboard --extra visual --reinstall-package blinker
  ```
- **Smoke check 4 fails with `404 … Dataset … not found`:** `BQ_GOLD_DATASET` /
  `BQ_LOCATION` are wrong or Gold isn't built. Checks 1–3 still pass (the
  server boots fine without touching BigQuery).
- **"server did not become healthy within 90s":** read
  `artifacts/dashboard_smoke_server.log` (or `dashboard_visual_server.log`) for
  the boot traceback.

## The drivers

- `scripts/dashboard_smoke.py` — Tier-1 HTTP/callback harness (also used as the
  post-deploy gate in `scripts/dashboard-deploy.ps1`).
- `scripts/dashboard_visual_check.py` — Tier-2 Playwright screenshots; imports
  the launch/teardown helpers from `dashboard_smoke.py`.
