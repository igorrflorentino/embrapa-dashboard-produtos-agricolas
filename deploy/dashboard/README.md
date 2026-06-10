# Dashboard — Cloud Run Service

Packages the Dash dashboard (the Claude Design System reimplementation: PEVS +
trade + Multi-fonte) as a long-running **Cloud Run Service**, served by
**gunicorn**. It reads the prod `serving` marts and `gold` reference tables on
demand (Pushdown Computing) and never holds Gold in memory.

> **Service, not Job.** This is the always-on HTTP image. It is **not** the batch
> ingestion image (that lives in [`../ingestion/`](../ingestion/), runs the CLI to
> completion, and exits with no HTTP port). Don't confuse the two `Dockerfile`s.

| | **Service** (this dir) | **Job** ([`../ingestion`](../ingestion)) |
|---|---|---|
| Nature | always-on, scales to zero | batch, ephemeral |
| HTTP port | yes (gunicorn on `$PORT`) | none |
| Trigger | user request (private; IAP later) | Cloud Scheduler (cron) |
| Runtime SA | `sa-web-dashboard-prod` (read serving + gold) | `sa-data-pipeline-prod` (write GCS+BQ) |

## How it serves

- **gunicorn** binds the Dash app's Flask `server` on `$PORT` (Cloud Run injects
  `8080`). One worker keeps the per-process `flask-caching` `SimpleCache` coherent
  within an instance; Cloud Run scales by **adding instances**, which converge via
  the cache TTL (eventual consistency — no shared Redis needed; see
  `src/embrapa_commodities/serving/cache.py`). Threads serve the concurrent,
  I/O-bound BigQuery reads.
- **Stateless**: all UI state lives in the browser (`dcc.Store`); any instance can
  serve any request, so scale-to-zero and autoscaling are free.
- **No BigQuery I/O at import** — importing `app:server` only binds the cache, so
  cold starts stay fast; the first query runs on the first request.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | The service image (`uv sync --extra dashboard`, gunicorn entrypoint). |
| `cloudbuild.yaml` | Builds the image from the repo root via Cloud Build. |
| `deploy.sh` | Build + create/update the Cloud Run Service (**private**). Reads `.env`. |

## One-time prerequisites

```bash
# 1) Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# 2) Provision the runtime SA + its least-privilege grants (idempotent):
#      READ 'serving' + 'gold', APPEND 'research_inputs', project bigquery.jobUser
make iam-grant            # DRY_RUN=1 make iam-grant   to preview
```

The runtime SA (`sa-web-dashboard-prod`) reads BigQuery **as itself** via ADC — no
keyfile, no impersonation. `GCP_IMPERSONATION_SA` is intentionally **not** shipped
to the service (it would make the app try to impersonate another SA).

## Deploy

From the repo root (config is read from `.env` — the same source the CLI uses):

```bash
make dashboard-deploy        # build image + create/update the service (private)
```

`deploy.sh` forwards config via an **explicit allowlist** — only the keys the
dashboard reads at runtime: `GCP_PROJECT_ID`, `BQ_LOCATION`, `CACHE_*`,
`IAP_AUDIENCE`, `COMTRADE_BRAZIL_ISO`. The dataset names `BQ_GOLD_DATASET` /
`BQ_SERVING_DATASET` are **forced to prod** (`gold` / `serving`), *not* read from
`.env` — a developer's local `.env` often points them at the **auto-expiring dev
datasets** (e.g. `BQ_GOLD_DATASET=dbt_dev_gold`, 7-day TTL), which would silently
break the prod service. Override with `DASHBOARD_GOLD_DATASET` /
`DASHBOARD_SERVING_DATASET` only to deploy a deliberately dev-pointed service. The
secret `COMTRADE_API_KEY`, `GCP_IMPERSONATION_SA`, the dev-only
`CURATION_DEV_AUTHOR`, ingestion/dbt vars, and everything else in `.env` are
**not** shipped.

## Auth — the service is deployed PRIVATE

`deploy.sh` deploys with `--no-allow-unauthenticated` **and** enforces the invoker
IAM check. Both are required: the `run.googleapis.com/invoker-iam-disabled`
annotation can silently bypass IAM even after `--no-allow-unauthenticated`. After
deploy the service is **not** publicly reachable. To use it:

```bash
# As a developer — proxy through your own gcloud identity:
gcloud run services proxy embrapa-dashboard --region <DASHBOARD_REGION> --project <GCP_PROJECT_ID>
#   → open http://localhost:8080

# Grant a specific person/group invoker access:
gcloud run services add-iam-policy-binding embrapa-dashboard --region <DASHBOARD_REGION> \
  --member='user:someone@example.com' --role=roles/run.invoker
```

**End-user browser SSO (follow-up):** front the service with an External HTTPS
Load Balancer + **IAP** (serverless NEG → backend service → IAP). IAP authenticates
Google accounts in the browser and injects the signed `X-Goog-IAP-JWT-Assertion`.
Set `IAP_AUDIENCE` in `.env` (the backend-service audience) so the app verifies
that JWT — the curation writer uses the verified email as the audit author
(`src/embrapa_commodities/serving/iap.py`). Curation itself ships with the M3
"Curadoria" view; until then the dashboard is read-only.

## Tunable knobs (optional `.env` overrides)

All have sensible defaults; set them in `.env` only to override:

| Var | Default | Meaning |
|---|---|---|
| `DASHBOARD_REGION` | `us-central1` | Cloud Run region (a **single** region). Decoupled from `BQ_LOCATION` — Cloud Run rejects a BigQuery multi-region like `US`/`EU` (those two are mapped; any other bare multi-region errors). |
| `DASHBOARD_SERVICE_NAME` | `embrapa-dashboard` | Service name |
| `DASHBOARD_AR_REPO` | `embrapa-services` | Artifact Registry repo (separate from the jobs' `embrapa-jobs`) |
| `DASHBOARD_SA` | `sa-web-dashboard-prod@<project>…` | Runtime service account |
| `DASHBOARD_MEMORY` / `DASHBOARD_CPU` | `1Gi` / `1` | Resources per instance |
| `DASHBOARD_CONCURRENCY` | `8` | Requests per instance |
| `DASHBOARD_MIN_INSTANCES` / `DASHBOARD_MAX_INSTANCES` | `0` / `4` | Autoscaling bounds (0 = scale to zero) |
| `WEB_CONCURRENCY` / `GUNICORN_THREADS` | `1` / `8` | gunicorn workers/threads (image env) |

## Notes & troubleshooting

- **Logs:** `gcloud run services logs read embrapa-dashboard --region <DASHBOARD_REGION>`.
- **403 on `gold` reads:** the runtime SA is missing `gold` READER — re-run
  `make iam-grant` (it grants READER on both `serving` and `gold`).
- **Local run:** `make dashboard-run` serves the same app on `:8050` via Dash's
  dev server (needs `.env` + ADC) — no container, for quick iteration.
- **Assets:** the image installs the package **editable**, so Dash serves
  `assets/` (CSS, fonts, logos) from the in-image source tree.
