# `scripts/` — operational tooling

Helper scripts that sit alongside the Python package. Each script is short
and single-purpose; the heavy logic lives in `src/embrapa_commodities/`. This
README is the index — for behaviour details, open the script and read its
header comment / docstring (which is also the source for every description
below).

Three groups, distinguished by audience:

- **Local dev / setup** — run once per machine when you start contributing.
- **Dashboard run / build / deploy** — daily-driver workflows for the Dash app.
- **GCP IAM / service accounts** — one-shots run by the project owner.

The `.ps1` files are **Windows PowerShell** wrappers that exist as a
convenience for this Windows-first repo. They all delegate to the same Python
entry points (or `gcloud`) that the cross-platform paths use, so on
macOS/Linux you can ignore them and go straight to `make <target>` or
`uv run python scripts/<name>.py`.

---

## Local dev / setup

| Script | Platform | What it does | When to run | Invoked by |
|---|---|---|---|---|
| [`setup_dev_env.py`](setup_dev_env.py) | Cross-platform (Python 3) | Cross-platform development environment setup. Auto-detects auth mode (SA impersonation → `GOOGLE_APPLICATION_CREDENTIALS` → `--credentials-file` → interactive paste) and generates `.env`, `~/.dbt/profiles.yml`, and credential files for the detected mode. | Once per machine, immediately after cloning, to bootstrap the dev environment. Also re-run after switching auth modes. | `setup.sh`, `setup.ps1`, `init_dev_env.sh`; documented in [docs/setup.md](../docs/setup.md). |
| [`test_setup.py`](test_setup.py) | Cross-platform (Python 3) | Comprehensive test suite that validates the development environment after `setup_dev_env.py` ran — checks `.env`, dbt profile, ADC credentials, BigQuery connectivity, and required Python modules. | After running setup (manually or via `setup.sh`/`setup.ps1`) to confirm everything works before you start writing code. | `test.sh`, `test.bat`, `init_dev_env.sh`; documented in [docs/testing.md](../docs/testing.md). |
| [`check_dashboard_size.py`](check_dashboard_size.py) | Cross-platform (Python 3) | Soft 500-LOC ceiling for files under `src/embrapa_commodities/dashboard/`. Pre-commit hook that fails when a dashboard module exceeds the limit and is not on the audit-introduced allowlist. Allowlist is **self-pruning**: if a grandfathered file drops back under 500 LOC, the hook fails until you remove it from the list. | Automatically on every commit that stages a dashboard file (via the `local` hook in `.pre-commit-config.yaml`). Audit-introduced — see [docs/audit_2026-05.md](../docs/audit_2026-05.md) § 2.1 / Action item #7. | `pre-commit` (`.pre-commit-config.yaml` local hook). |

## Dashboard run / build / deploy

| Script | Platform | What it does | When to run | Invoked by |
|---|---|---|---|---|
| [`dashboard-run.ps1`](dashboard-run.ps1) | Windows PowerShell | Runs the Dash dashboard locally on `http://localhost:8080`. Reads `GCP_PROJECT_ID` (and other settings) from `.env` via pydantic-settings. Thin wrapper around `uv run … python -m embrapa_commodities.dashboard.app`. | Local dev — when you want a live server to click around in. | Alternative to `make dashboard-run`. Documented in the `run-dashboard` skill. |
| [`dashboard_smoke.py`](dashboard_smoke.py) | Cross-platform (Python 3) | HTTP + callback smoke test (stdlib only). Five checks: `/_health` 200, `/` 200, `/_dash-dependencies` non-empty, live BigQuery route render, **and** an unauthenticated `/_health` against Cloud Run returning 403 (asserts the IAM gate is closed). Auto-mints a Google identity token via `gcloud auth print-identity-token` for `*.run.app` targets; pass `--no-auth` to skip (e.g. when testing the 403 path itself). | Pre-commit / pre-deploy gate; also as a post-deploy gate against the prod URL (`--no-launch --url …`). | `make dashboard-smoke`, [`dashboard-smoke.ps1`](dashboard-smoke.ps1), and `dashboard-deploy.ps1` (post-deploy gate). Documented in the `run-dashboard`, `dash-page-scaffold`, and `deploy-cloud-run` skills. |
| [`dashboard-smoke.ps1`](dashboard-smoke.ps1) | Windows PowerShell | Thin wrapper that `uv sync --extra dashboard`s and then runs `scripts/dashboard_smoke.py`, passing extra args through (e.g. `--no-launch --url https://…`). | Same as `dashboard_smoke.py` — the wrapper exists so Windows users don't have to remember the extras flag. | Documented in the `run-dashboard` skill. |
| [`dashboard_visual_check.py`](dashboard_visual_check.py) | Cross-platform (Python 3) | Tier-2 headless-browser check. Loads each key view in real Chromium, asserts no error overlay, asserts content rendered, and writes screenshots to `artifacts/`. Requires the `visual` extra (Playwright). | Before a release, or any time you want eyeballable visual evidence that views still render. First run downloads Chromium (~150 MB). | `make dashboard-visual`, [`dashboard-visual.ps1`](dashboard-visual.ps1). Documented in the `run-dashboard` skill. |
| [`dashboard-visual.ps1`](dashboard-visual.ps1) | Windows PowerShell | Wrapper that syncs both `dashboard` + `visual` extras, runs `playwright install chromium` (idempotent), then calls `scripts/dashboard_visual_check.py`. | Same as `dashboard_visual_check.py`. | Documented in the `run-dashboard` skill. |
| [`dashboard-build.ps1`](dashboard-build.ps1) | Windows PowerShell | **Optional.** Builds the Cloud Run container image locally from `./Dockerfile`. Tag configurable via `$env:DASH_IMAGE` (default `embrapa-dashboard:local`). | Only if you want to smoke-test the container image on your machine before deploying — `dashboard-deploy.ps1` builds remotely via Cloud Build, so you can usually skip this. | Standalone (alternative to `make dashboard-build`). |
| [`dashboard-deploy.ps1`](dashboard-deploy.ps1) | Windows PowerShell | Deploys the Dash dashboard to Cloud Run (`gcloud run deploy --source .`, so build happens in Cloud Build). Auth posture is **private**: passes both `--no-allow-unauthenticated` (removes the `allUsers` IAM binding) and `--invoker-iam-check` (clears the `invoker-iam-disabled` annotation that bypasses IAM entirely) — see `docs/auth.md`. Reads `GCP_PROJECT_ID`; optional `DASH_SERVICE` (default `embrapa-dashboard-commodities`), `DASH_REGION`, `BQ_LOCATION`, `DASH_SA`. | When shipping a release. Pair with `dashboard-setup-sa.ps1` first for a least-privilege runtime SA, and grant `roles/run.invoker` to whoever should reach the service. | Documented in the `deploy-cloud-run` skill. |

## GCP IAM / service accounts

| Script | Platform | What it does | When to run | Invoked by |
|---|---|---|---|---|
| [`dashboard-setup-sa.ps1`](dashboard-setup-sa.ps1) | Windows PowerShell | Idempotently provisions a dedicated, least-privilege Cloud Run runtime SA (`dashboard-runtime` by default). Grants `roles/bigquery.dataViewer` on the gold dataset only + `roles/bigquery.jobUser` at project level. | Once per GCP project, **before** the first `dashboard-deploy.ps1` if you want a dedicated runtime SA instead of the default Compute Engine SA. | Documented in the `deploy-cloud-run` skill. |
| [`grant-sa-iam-roles.ps1`](grant-sa-iam-roles.ps1) | Windows PowerShell | Grants `roles/bigquery.user`, `bigquery.dataEditor`, `storage.objectViewer`, and `serviceusage.serviceUsageConsumer` to `sa-secret-reader-prod@…` on the project (the SA used by `setup_dev_env.py`'s impersonation path). | Once per GCP project, by the project owner, to bootstrap the impersonation target SA used during local dev. | Standalone one-shot (see [docs/iam_setup.md](../docs/iam_setup.md)). |
| [`setup-claude-code-web-sa.sh`](setup-claude-code-web-sa.sh) | Bash (macOS / Linux / Cloud Shell) | Creates `sa-claude-code-web-dev` SA + JSON keyfile, granting BigQuery `dataEditor` and job-runner roles. Output keyfile (`sa-claude-code-web-dev-key.json`) is base64-encoded and pasted into Claude Code Web env vars. | Once per GCP project, only if you want a limited-scope SA for Claude Code Web sandbox (no prod access). | Standalone one-shot. |

---

## Conventions

- **Read the header.** Every script starts with a comment block (`.ps1`) or
  module docstring (`.py`) that documents required env vars, optional env
  vars, and a usage example. If something here is out of date, that header
  is the source of truth — please update both.
- **Idempotent IAM.** All three SA scripts are safe to re-run; they detect
  existing SAs / bindings and skip them.
- **`.ps1` and `make` are interchangeable** for the dashboard workflows.
  Both call `uv run … python …` under the hood. Pick whichever fits your
  shell.
