# `scripts/` — operational tooling

Helper scripts that sit alongside the Python package. Each script is short
and single-purpose; the heavy logic lives in `src/embrapa_commodities/`. This
README is the index — for behaviour details, open the script and read its
header comment / docstring (which is also the source for every description
below).

Two groups, distinguished by audience:

- **Local dev / setup** — run once per machine when you start contributing.
- **GCP IAM / service accounts** — one-shots run by the project owner.

> ⚠️ **Frontend em reconstrução.** Os scripts de run / build / deploy do
> dashboard Dash (`dashboard-*.ps1`, `dashboard_smoke.py`,
> `dashboard_visual_check.py`, `check_dashboard_size.py`,
> `dashboard-setup-sa.ps1`) foram removidos em 2026-05-29 junto com a UI.
> O próximo handoff do Claude Design System trará a nova camada de
> tooling de frontend.

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

## GCP IAM / service accounts

| Script | Platform | What it does | When to run | Invoked by |
|---|---|---|---|---|
| [`grant-sa-iam-roles.ps1`](grant-sa-iam-roles.ps1) | Windows PowerShell | Grants `roles/bigquery.user`, `bigquery.dataEditor`, `storage.objectViewer`, and `serviceusage.serviceUsageConsumer` to `sa-secret-reader-prod@…` on the project (the SA used by `setup_dev_env.py`'s impersonation path). | Once per GCP project, by the project owner, to bootstrap the impersonation target SA used during local dev. | Standalone one-shot (see [docs/iam_setup.md](../docs/iam_setup.md)). |
| [`setup-claude-code-web-sa.sh`](setup-claude-code-web-sa.sh) | Bash (macOS / Linux / Cloud Shell) | Creates `sa-claude-code-web-dev` SA + JSON keyfile, granting BigQuery `dataEditor` and job-runner roles. Output keyfile (`sa-claude-code-web-dev-key.json`) is base64-encoded and pasted into Claude Code Web env vars. | Once per GCP project, only if you want a limited-scope SA for Claude Code Web sandbox (no prod access). | Standalone one-shot. |

---

## Conventions

- **Read the header.** Every script starts with a comment block (`.ps1`) or
  module docstring (`.py`) that documents required env vars, optional env
  vars, and a usage example. If something here is out of date, that header
  is the source of truth — please update both.
- **Idempotent IAM.** Both SA scripts are safe to re-run; they detect
  existing SAs / bindings and skip them.
