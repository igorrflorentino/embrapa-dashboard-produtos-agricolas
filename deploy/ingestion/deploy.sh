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

# Resolve the Cloud Run region. Cloud Run requires a SINGLE region (e.g.
# us-central1) and rejects a BigQuery multi-region locator like "US"/"EU" —
# `gcloud run jobs deploy --region US` fails. So INGEST_JOB_REGION is a
# first-class input, DECOUPLED from BQ_LOCATION, defaulting to us-central1.
# As a convenience, an explicitly-set multi-region locator is mapped to a
# concrete region; a bare/unmapped multi-region is rejected with a clear error
# rather than passed through to gcloud (which would fail cryptically).
resolve_region() {
  local r="${INGEST_JOB_REGION:-}"
  if [ -z "$r" ]; then
    echo us-central1
    return 0
  fi
  case "$r" in
    US|us) echo us-central1 ;;       # BigQuery "US" multi-region → default Cloud Run region
    EU|eu) echo europe-west1 ;;      # BigQuery "EU" multi-region → a concrete EU region
    *-*)   echo "$r" ;;              # already a concrete region (has a hyphen, e.g. us-east1)
    *)
      echo "ERROR: INGEST_JOB_REGION='$r' is not a Cloud Run region. Cloud Run needs a" >&2
      echo "       single region (e.g. us-central1, europe-west1), not a multi-region." >&2
      echo "       Set INGEST_JOB_REGION explicitly in .env (it is decoupled from BQ_LOCATION)." >&2
      exit 1
      ;;
  esac
}

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="$(INGEST_JOB_REGION="${INGEST_JOB_REGION:-$(get_env INGEST_JOB_REGION)}" resolve_region)"
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

# 3) Build the Job env vars from .env via an EXPLICIT ALLOWLIST — forward ONLY
#    the keys `embrapa ingest all` actually reads, not the whole .env. The job
#    runs AS the ingestion SA (no impersonation, no API key) and is a batch with
#    no UI, so the serving/cache/dbt and deploy-time INGEST_*/INGEST_SCHEDULE_*
#    vars are irrelevant to it; shipping them would only leak config surface
#    into the Job's environment. COMTRADE is excluded from `ingest all`
#    (key-gated), so its Bronze/scope vars are omitted too. A YAML file handles
#    values with commas/colons (e.g. BCB_INFLATION_SERIES=433:IPCA,189:IGPM).
#
# Allowlist (anchored, prefix-based so new per-source knobs are auto-covered):
#   GCP_PROJECT_ID, GCS_*                       — project + landing/raw bucket + prefixes
#   BQ_LOCATION                                 — dataset region
#   BQ_BRONZE_{IBGE,BCB,COMEX}_*                — Bronze dataset/table names for the
#                                                 sources `all` runs (NOT COMTRADE:
#                                                 it is key-gated and excluded from `all`)
#   IBGE_* / BCB_* / COMEX_*                     — per-source scope (codes, years, flows, delta)
INGEST_ALLOWLIST='^(GCP_PROJECT_ID|GCS_[A-Z0-9_]+|BQ_LOCATION|BQ_BRONZE_(IBGE|BCB|COMEX)_[A-Z0-9_]+|IBGE_[A-Z0-9_]+|BCB_[A-Z0-9_]+|COMEX_[A-Z0-9_]+)='
ENV_YAML="$(mktemp)"; trap 'rm -f "$ENV_YAML"' EXIT
grep -E "$INGEST_ALLOWLIST" "$ENV_FILE" \
  | while IFS='=' read -r key val; do
      printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')"
    done > "$ENV_YAML"
[ -s "$ENV_YAML" ] || { echo "ERROR: no ingestion config matched in $ENV_FILE (check GCP_PROJECT_ID etc.)"; exit 1; }

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
