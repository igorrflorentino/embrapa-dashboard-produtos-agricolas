# Ingestion — Cloud Run Job + Cloud Scheduler

Packages `embrapa ingest all` as a **Cloud Run Job** (batch) triggered by
**Cloud Scheduler** in the early morning. This automates the Bronze refresh that
feeds Silver → Gold → the `serving` marts.

> **Job, not Service.** This is the *batch ingestion* image — it runs the CLI to
> completion and exits, with no HTTP port. It is **not** the dashboard, which is
> a long-running Cloud Run *Service* and arrives with the Claude Design System
> handoff. Don't confuse this `Dockerfile` with the (still-pending) dashboard one.

| | **Job** (this dir) | **Service** (dashboard, later) |
|---|---|---|
| Nature | batch, ephemeral | always-on, scales to zero |
| HTTP port | none | yes (Gunicorn) |
| Trigger | Cloud Scheduler (cron) | user request (behind IAP) |
| Runtime SA | `sa-data-pipeline-prod` (write GCS+BQ) | `sa-web-dashboard-prod` (read serving) |

## Why this is safe to run unattended

`ingest all` is built for a blind cron:

- **`tenacity` retries** (`core.http.http_retry_policy`: `stop_after_attempt(5)` +
  exponential backoff + a wall-clock slow-byte drain) reabsorb transient upstream
  failures (HTTP 5xx, timeouts, stalled reads).
- **Delta by default** — IBGE re-fetches only recent years (from
  `latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS`), BCB pulls a small overlap
  window, COMEX re-downloads only on ETag change. No leg re-pulls its whole
  history, so re-running is cheap and idempotent enough for cron.
- **COMTRADE is excluded** from `all` (key-gated), so the job needs **no secret** —
  only the runtime SA's GCP credentials.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | The job image (`uv sync --no-dev`, runs `embrapa ingest all`). |
| `cloudbuild.yaml` | Builds the image from the repo root via Cloud Build. |
| `deploy.sh` | Build + create/update the Cloud Run Job. Reads `.env`. |
| `schedule.sh` | Create/update the nightly Cloud Scheduler trigger. |

## One-time prerequisites

```bash
# Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com

# The runtime SA (write GCS + BQ) — see docs/iam_setup.md. Typically:
#   roles/storage.objectAdmin, roles/bigquery.dataEditor, roles/bigquery.jobUser
```

## Deploy

From the repo root (config is read from `.env` — the same single source of truth
the CLI uses):

```bash
make ingest-job-deploy        # build image + create/update the job
# then run it once to validate:
gcloud run jobs execute embrapa-ingest-all --region <BQ_LOCATION> --project <GCP_PROJECT_ID>
```

`deploy.sh` forwards the non-secret `.env` config to the job as env vars and
**drops** `COMTRADE_API_KEY`, `GCP_IMPERSONATION_SA`, and the dashboard-only
`CACHE_REDIS_URL` / `CURATION_DEV_AUTHOR`. The job runs **as** the ingestion SA,
so it authenticates via the runtime identity — no keyfile, no impersonation.

## Schedule

```bash
make ingest-job-schedule      # 05:00 America/Sao_Paulo daily by default
# grant the scheduler SA permission to run the job (one-time):
gcloud run jobs add-iam-policy-binding embrapa-ingest-all \
  --region <BQ_LOCATION> --project <GCP_PROJECT_ID> \
  --member "serviceAccount:sa-data-pipeline-prod@<GCP_PROJECT_ID>.iam.gserviceaccount.com" \
  --role roles/run.invoker
```

## Tunable knobs (optional `.env` overrides)

All have sensible defaults; set them in `.env` only to override:

| Var | Default | Meaning |
|---|---|---|
| `INGEST_JOB_REGION` | `BQ_LOCATION` | Cloud Run region |
| `INGEST_JOB_NAME` | `embrapa-ingest-all` | Job name |
| `INGEST_JOB_AR_REPO` | `embrapa-jobs` | Artifact Registry repo |
| `INGEST_JOB_SA` | `sa-data-pipeline-prod@<project>…` | Runtime service account |
| `INGEST_JOB_TASK_TIMEOUT` | `3600s` | Max wall-clock per run |
| `INGEST_JOB_MEMORY` / `INGEST_JOB_CPU` | `2Gi` / `1` | Resources |
| `INGEST_SCHEDULE_CRON` | `0 5 * * *` | Cron expression |
| `INGEST_SCHEDULE_TZ` | `America/Sao_Paulo` | Schedule timezone |

## Notes & troubleshooting

- **Single source per run:** override the command to ingest just one source, e.g.
  `gcloud run jobs execute embrapa-ingest-all --args=ibge …` (the entrypoint is
  `embrapa ingest`, so `--args ibge` runs `embrapa ingest ibge`).
- **First historical backfill:** the nightly job is **delta** (recent years
  only), so it never does the full IBGE/COMEX history. Seed the history once
  locally (`make ingest-ibge-historical` for IBGE; a `--full` COMEX run) — then
  the job keeps it current via delta.
- **Logs:** `gcloud run jobs executions list --job embrapa-ingest-all …` then
  `gcloud run jobs executions describe <execution> …`. The pipeline also emits
  structured events consumable by `embrapa monitor`.
