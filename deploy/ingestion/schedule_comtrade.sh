#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Create/update the MONTHLY UN Comtrade ingestion Cloud Scheduler trigger.
#
# UN Comtrade is the one source EXCLUDED from the nightly `ingest all`
# (cli.IngestSpec in_all=False): it is API-key-gated AND quota-gated (the free UN
# Comtrade API throttles hard — a full 1988→present backfill across 252 reporters
# cannot finish in one pass). So Comtrade Gold ships with only a partial window
# (currently 2022–2023) and the banco stays `maturity: 'beta'` until the history
# is filled.
#
# This trigger runs the SAME Job (embrapa-ingest-all) but overrides its container
# args to `["comtrade"]` → `embrapa ingest comtrade`. The pipeline is chunked by
# (year, reporter-batch) and RESUME-AWARE (it skips chunks already in Bronze), so
# each monthly run chips away at the historical backlog within that day's quota
# and refreshes recent years. Over several months the backfill completes; flip
# `un_comtrade` to `maturity: 'estavel'` once Gold covers the advertised window.
#
# PREREQUISITE — the Job needs the UN key at runtime (it cannot read it from .env):
#   1) Store the key (free from comtradedeveloper.un.org) in Secret Manager:
#        gcloud secrets create comtrade-un-key --replication-policy=automatic --project "$PROJECT"
#        printf '%s' 'YOUR_UN_KEY' | gcloud secrets versions add comtrade-un-key --data-file=- --project "$PROJECT"
#   2) Grant the Job's RUNTIME SA read access to that secret:
#        gcloud secrets add-iam-policy-binding comtrade-un-key --project "$PROJECT" \
#          --member "serviceAccount:<INGEST_JOB_RUNTIME_SA>" --role roles/secretmanager.secretAccessor
#   3) Point COMTRADE_KEY_SECRET (in .env) at that secret's NAME and redeploy the
#      Job — deploy.sh mounts it when COMTRADE_KEY_SECRET is set:
#        make ingest-job-deploy
#
# Same v2 `:run` overrides mechanism + the run.jobs.runWithOverrides IAM note as
# schedule_reconcile.sh. Run by the OPERATOR. Idempotent.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found"; exit 1; }
get_env() { { grep -E "^$1=" "$ENV_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

resolve_region() {
  local r="${INGEST_JOB_REGION:-}"
  if [ -z "$r" ]; then echo us-central1; return 0; fi
  case "$r" in
    US|us) echo us-central1 ;;
    EU|eu) echo europe-west1 ;;
    *-*)   echo "$r" ;;
    *)
      echo "ERROR: INGEST_JOB_REGION='$r' is not a Cloud Run region." >&2
      exit 1 ;;
  esac
}

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="$(INGEST_JOB_REGION="${INGEST_JOB_REGION:-$(get_env INGEST_JOB_REGION)}" resolve_region)"
JOB_NAME="${INGEST_JOB_NAME:-$(get_env INGEST_JOB_NAME)}"
JOB_NAME="${JOB_NAME:-embrapa-ingest-all}"

SCHED_NAME="${COMTRADE_SCHEDULE_NAME:-$(get_env COMTRADE_SCHEDULE_NAME)}"
SCHED_NAME="${SCHED_NAME:-${JOB_NAME}-comtrade-monthly}"
# Monthly, 15th at 04:00 BRT — mid-month, away from the 1st-of-month reconcile
# (03:00). NOTE: with the default 6h task timeout below, a long run is STILL in
# flight during the 05:00 BRT nightly `ingest all` and the 08:30 BRT scheduled
# prod dbt build. That concurrency is safe — different Bronze tables, and dbt
# only reads Bronze — but a partially ingested Comtrade year can reach
# Silver/Gold one build early; the next daily build converges it.
CRON="${COMTRADE_SCHEDULE_CRON:-$(get_env COMTRADE_SCHEDULE_CRON)}"
CRON="${CRON:-0 4 15 * *}"
SCHED_TZ="${COMTRADE_SCHEDULE_TZ:-$(get_env COMTRADE_SCHEDULE_TZ)}"
SCHED_TZ="${SCHED_TZ:-America/Sao_Paulo}"
SCHED_SA="${INGEST_SCHEDULE_SA:-$(get_env INGEST_SCHEDULE_SA)}"
SCHED_SA="${SCHED_SA:-sa-data-pipeline-prod@${PROJECT}.iam.gserviceaccount.com}"
# Comtrade walks many (year, reporter) chunks within the API quota — give it the
# max task timeout so a single run gets through as much backlog as the quota allows.
TASK_TIMEOUT="${COMTRADE_JOB_TASK_TIMEOUT:-$(get_env COMTRADE_JOB_TASK_TIMEOUT)}"
TASK_TIMEOUT="${TASK_TIMEOUT:-21600s}"

URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB_NAME}:run"

# Override CMD ["all"] → ["comtrade"]; ENTRYPOINT ["embrapa","ingest"] stays, so
# the container runs `embrapa ingest comtrade` (resume-aware, key-gated).
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" <<JSON
{"overrides":{"containerOverrides":[{"args":["comtrade"]}],"timeout":"${TASK_TIMEOUT}","taskCount":1}}
JSON

if gcloud scheduler jobs describe "$SCHED_NAME" \
     --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

echo "${ACTION^} scheduler '$SCHED_NAME': '$CRON' ($SCHED_TZ) → run '$JOB_NAME' as comtrade (timeout ${TASK_TIMEOUT})"
gcloud scheduler jobs "$ACTION" http "$SCHED_NAME" --project "$PROJECT" --location "$REGION" \
  --schedule "$CRON" --time-zone "$SCHED_TZ" \
  --uri "$URI" --http-method POST \
  --headers "Content-Type=application/json" \
  --message-body-from-file "$BODY_FILE" \
  --oauth-service-account-email "$SCHED_SA"

cat <<EOF

Scheduled the MONTHLY Comtrade ingest. Before it can succeed, ensure (one-time):
  • the UN key secret exists + the Job runtime SA has secretAccessor on it
    (see the PREREQUISITE block at the top of this script),
  • COMTRADE_KEY_SECRET in .env points at that secret name, and the Job was
    redeployed to mount it:  make ingest-job-deploy
  • the scheduler SA can override args (same as reconcile):
      gcloud run jobs add-iam-policy-binding $JOB_NAME --region $REGION --project $PROJECT \\
        --member "serviceAccount:$SCHED_SA" --role roles/run.jobsExecutorWithOverrides

Trigger a first backfill run now (chips away within today's UN API quota):
  gcloud scheduler jobs run $SCHED_NAME --location $REGION --project $PROJECT
Or directly:
  gcloud run jobs execute $JOB_NAME --region $REGION --project $PROJECT --args=comtrade

NOTE: refreshes only BRONZE. Silver/Gold update on the next scheduled dbt build.
Once Gold covers the advertised window, flip un_comtrade maturity 'beta'→'estavel'
in frontend/src/proto/bancos.js.
EOF
