---
name: deploy-cloud-run
description: >-
  Deploy the dashboard to Google Cloud Run, build the Docker image, run
  pre-deploy checks, or verify the production service. Use when asked to
  deploy, push to production, build the container, check the live service,
  or gate a release.
---

# Deploy to Cloud Run — Embrapa Dashboard

## Full Deploy Flow

```
lint → test → smoke (local) → git commit → deploy → post-deploy smoke
```

## Quick Commands

```powershell
# 1. Pre-flight checks
make lint                   # ruff check + format --check
make test                   # pytest
uv run --extra dashboard python scripts/dashboard_smoke.py   # smoke test (live BQ)

# 2. Build Docker image locally (optional, for local testing)
make dashboard-build        # docker build -t embrapa-dashboard:local .

# 3. Deploy to Cloud Run (uses gcloud's active project)
make dashboard-deploy
# OR the PowerShell script with post-deploy gate:
.\scripts\dashboard-deploy.ps1

# 4. Post-deploy verification
uv run --extra dashboard python scripts/dashboard_smoke.py \
  --no-launch --url https://embrapa-dashboard-commodities-aq63dvcryq-uc.a.run.app
```

## Cloud Run Configuration

| Setting | Value |
|---------|-------|
| Service name | `embrapa-dashboard-commodities` |
| Region | `us-central1` |
| Memory | 1 GiB |
| CPU | 1 |
| Min instances | 0 |
| Max instances | 5 |
| Port | 8080 |
| CPU boost | enabled |
| Auth | `--no-allow-unauthenticated` (gated by `roles/run.invoker` — see [`docs/auth.md`](../../../docs/auth.md)) |

Environment variables set on the service:
```
GCP_PROJECT_ID=$GCP_PROJECT_ID
BQ_GOLD_DATASET=gold
BQ_LOCATION=${BQ_LOCATION:-us-central1}
CLOUD_RUN_REGION=us-central1
```

## Production URL

```
https://embrapa-dashboard-commodities-aq63dvcryq-uc.a.run.app/
```

Key routes:
- `/_health` → `{"status":"ok"}` (health check — NOT `/healthz`, which Google Frontend reserves)
- `/ibge-pevs/visao-geral` → default view (the `/` path redirects here)
- `/status` → system health dashboard

## PowerShell Scripts (in `scripts/`)

| Script | Purpose |
|--------|---------|
| `dashboard-build.ps1` | Build Docker image locally |
| `dashboard-deploy.ps1` | Full deploy + post-deploy smoke gate |
| `dashboard-smoke.ps1` | Smoke test wrapper (auto `uv sync`) |
| `dashboard-visual.ps1` | Visual test with screenshots |
| `dashboard-setup-sa.ps1` | Configure service account IAM |

## Pre-Deploy Checklist

1. [ ] `make lint` passes (ruff check + format)
2. [ ] `make test` passes (pytest)
3. [ ] `dashboard_smoke.py` — all 4 checks pass:
   - Check 1: `/_health` returns 200
   - Check 2: `GET /` returns 200
   - Check 3: `/_dash-dependencies` returns JSON
   - Check 4: POST route callback renders `/ibge-pevs/visao-geral` (forces live BQ load)
4. [ ] `git commit` all changes
5. [ ] Deploy via `make dashboard-deploy` or `dashboard-deploy.ps1`
6. [ ] Post-deploy smoke with `--no-launch --url <prod_url>`

## Troubleshooting

- **Deploy fails with "Permission denied"**: Check that the gcloud active account has `roles/run.admin` and `roles/iam.serviceAccountUser`.
- **Service returns 500 after deploy**: Check Cloud Run logs (`gcloud run logs read`). Usually `BQ_GOLD_DATASET` or `BQ_LOCATION` mismatch.
- **Health check passes but page is blank**: The error overlay catches layout exceptions and returns 200. Use the smoke test (check 4) or visual check to verify actual rendering.
- **"server did not become healthy within 90s"**: Read `artifacts/dashboard_smoke_server.log` for the boot traceback.

## Dockerfile Notes

The `Dockerfile` at repo root:
- Uses Python 3.12 base
- Installs only the `dashboard` extra (no dev deps)
- Runs via Gunicorn targeting `embrapa_commodities.dashboard.app:server`
- Exposes port 8080
