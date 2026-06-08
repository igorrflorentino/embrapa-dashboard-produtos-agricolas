#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Create/update the Cloud Scheduler trigger that runs the ingestion Job nightly.
#
# Cloud Scheduler hits the Cloud Run Admin API `jobs:run` endpoint with an OAuth
# token from a service account that holds roles/run.invoker on the job. Defaults
# to 05:00 America/Sao_Paulo (early morning / madrugada — low contention, off the
# analysis window). Idempotent.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found"; exit 1; }
get_env() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'; }

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="${INGEST_JOB_REGION:-$(get_env BQ_LOCATION)}"; REGION="${REGION:-us-central1}"
JOB_NAME="${INGEST_JOB_NAME:-embrapa-ingest-all}"
SCHED_NAME="${INGEST_SCHEDULE_NAME:-${JOB_NAME}-nightly}"
CRON="${INGEST_SCHEDULE_CRON:-0 5 * * *}"
SCHED_TZ="${INGEST_SCHEDULE_TZ:-America/Sao_Paulo}"
SCHED_SA="${INGEST_SCHEDULE_SA:-sa-data-pipeline-prod@${PROJECT}.iam.gserviceaccount.com}"

# Cloud Run Admin API v1 "run job" endpoint.
URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB_NAME}:run"

if gcloud scheduler jobs describe "$SCHED_NAME" \
     --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

echo "${ACTION^} scheduler '$SCHED_NAME': '$CRON' ($SCHED_TZ) → run '$JOB_NAME'"
gcloud scheduler jobs "$ACTION" http "$SCHED_NAME" --project "$PROJECT" --location "$REGION" \
  --schedule "$CRON" --time-zone "$SCHED_TZ" \
  --uri "$URI" --http-method POST \
  --oauth-service-account-email "$SCHED_SA"

cat <<EOF

Scheduled. The scheduler SA must hold run.invoker on the job:
  gcloud run jobs add-iam-policy-binding $JOB_NAME --region $REGION --project $PROJECT \\
    --member "serviceAccount:$SCHED_SA" --role roles/run.invoker
Trigger a test run immediately:
  gcloud scheduler jobs run $SCHED_NAME --location $REGION --project $PROJECT
EOF
