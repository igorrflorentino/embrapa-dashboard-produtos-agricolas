#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Build + deploy the `embrapa ingest all` Cloud Run JOB (batch, not a Service).
#
# Reads config from the repo-root .env (the project's single source of truth).
# Idempotent: re-running rebuilds the image and updates the job in place.
#
# Prereqs:
#   - gcloud authenticated, project APIs enabled: run, cloudbuild,
#     artifactregistry (cloudscheduler for schedule.sh).
#   - The ingestion SA exists (default sa-data-pipeline-prod) with write access
#     to GCS + BigQuery. See docs/iam_setup.md.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (copy .env.example → .env)"; exit 1; }

# Read a single value from .env without sourcing it (avoids bash interpreting
# odd values); strips a trailing CR so Windows CRLF files work too.
get_env() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'; }

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="${INGEST_JOB_REGION:-$(get_env BQ_LOCATION)}"; REGION="${REGION:-us-central1}"
JOB_NAME="${INGEST_JOB_NAME:-embrapa-ingest-all}"
AR_REPO="${INGEST_JOB_AR_REPO:-embrapa-jobs}"
INGEST_SA="${INGEST_JOB_SA:-sa-data-pipeline-prod@${PROJECT}.iam.gserviceaccount.com}"
TAG="${INGEST_JOB_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${JOB_NAME}:${TAG}"
TASK_TIMEOUT="${INGEST_JOB_TASK_TIMEOUT:-3600s}"
MEMORY="${INGEST_JOB_MEMORY:-2Gi}"
CPU="${INGEST_JOB_CPU:-1}"

echo "Project=$PROJECT  Region=$REGION  Job=$JOB_NAME"
echo "Image=$IMAGE"
echo "Runtime SA=$INGEST_SA"

# 1) Artifact Registry repo (idempotent).
if ! gcloud artifacts repositories describe "$AR_REPO" \
      --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repo '$AR_REPO'…"
  gcloud artifacts repositories create "$AR_REPO" --repository-format docker \
    --location "$REGION" --project "$PROJECT" \
    --description "Embrapa Cloud Run job images"
fi

# 2) Build + push the image via Cloud Build (no local Docker required).
echo "Building image via Cloud Build…"
gcloud builds submit "$REPO_ROOT" --project "$PROJECT" \
  --config "$REPO_ROOT/deploy/ingestion/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}"

# 3) Build the Job env vars from .env. Forward the non-secret config; the job
#    runs AS the ingestion SA, so it needs no impersonation and no API key
#    (COMTRADE is excluded from `ingest all`). A YAML file handles values with
#    commas/colons (e.g. BCB_INFLATION_SERIES=433:IPCA,189:IGPM) safely.
ENV_YAML="$(mktemp)"; trap 'rm -f "$ENV_YAML"' EXIT
grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" \
  | grep -vE '^(COMTRADE_API_KEY|GCP_IMPERSONATION_SA|CACHE_REDIS_URL|CURATION_DEV_AUTHOR)=' \
  | while IFS='=' read -r key val; do
      printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')"
    done > "$ENV_YAML"

# 4) Deploy / update the Cloud Run Job (create-or-update).
echo "Deploying Cloud Run Job…"
gcloud run jobs deploy "$JOB_NAME" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$INGEST_SA" \
  --env-vars-file "$ENV_YAML" \
  --task-timeout "$TASK_TIMEOUT" \
  --max-retries 1 \
  --memory "$MEMORY" \
  --cpu "$CPU"

cat <<EOF

Done. The job is deployed but NOT yet scheduled.
  Run once now:   gcloud run jobs execute $JOB_NAME --region $REGION --project $PROJECT
  Schedule nightly: deploy/ingestion/schedule.sh   (or: make ingest-job-schedule)
EOF
