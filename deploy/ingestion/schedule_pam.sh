#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Create/update the MONTHLY IBGE PAM ingestion Cloud Scheduler trigger.
#
# PAM (Produção Agrícola Municipal, SIDRA 5457) is EXCLUDED from the nightly
# `ingest all` (cli.IngestSpec in_all=False): it is ANNUAL, slow-changing data
# (~1yr publication lag), so a daily run would just re-scan the same Bronze for no
# benefit. A monthly cadence absorbs PAM's recent-year revisions and picks up a
# newly published year. (BCB stays daily via `ingest all`; PEVS/COMEX ride that
# daily job too — their delta is cheap. COMTRADE has its own monthly trigger.)
#
# This trigger runs the SAME Job (embrapa-ingest-all) but overrides its container
# args to `["ibge-pam"]` → `embrapa ingest ibge-pam`. The pipeline is delta-aware
# (re-fetches only PAM_DELTA_OVERLAP_YEARS back from the latest Bronze year), so
# the monthly run is small. The one-time FULL historical backfill (1974→) is a
# separate operator run: `uv run embrapa ingest ibge-pam --full` (heavy — chunk it
# if SIDRA's slow-byte deadline bites).
#
# PREREQUISITE — the Job must forward the PAM_* config. deploy.sh's INGEST_ALLOWLIST
# now includes PAM_* and BQ_BRONZE_PAM_*, so a plain `make ingest-job-deploy` after
# this change bakes PAM_PRODUCT_CODES / PAM_START_YEAR / … into the Job env. Without
# that redeploy the Job runs PAM on the config.py defaults (still correct, just not
# your .env overrides). PAM is keyless — no Secret Manager step (unlike Comtrade).
#
# Same v2 `:run` overrides mechanism + the run.jobs.runWithOverrides IAM note as
# schedule_comtrade.sh / schedule_reconcile.sh. Run by the OPERATOR. Idempotent.
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

SCHED_NAME="${PAM_SCHEDULE_NAME:-$(get_env PAM_SCHEDULE_NAME)}"
SCHED_NAME="${SCHED_NAME:-${JOB_NAME}-pam-monthly}"
# Monthly, 2nd at 04:00 BRT — after the 1st-of-month reconcile (03:00), away from
# the Comtrade trigger (15th). PAM is annual, so the exact day is not sensitive.
CRON="${PAM_SCHEDULE_CRON:-$(get_env PAM_SCHEDULE_CRON)}"
CRON="${CRON:-0 4 2 * *}"
SCHED_TZ="${PAM_SCHEDULE_TZ:-$(get_env PAM_SCHEDULE_TZ)}"
SCHED_TZ="${SCHED_TZ:-America/Sao_Paulo}"
SCHED_SA="${INGEST_SCHEDULE_SA:-$(get_env INGEST_SCHEDULE_SA)}"
SCHED_SA="${SCHED_SA:-sa-data-pipeline-prod@${PROJECT}.iam.gserviceaccount.com}"
# A delta PAM run is small; give it a comfortable ceiling for the occasional
# larger pull (a new year + revisions across all configured crops).
TASK_TIMEOUT="${PAM_JOB_TASK_TIMEOUT:-$(get_env PAM_JOB_TASK_TIMEOUT)}"
TASK_TIMEOUT="${TASK_TIMEOUT:-7200s}"

URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB_NAME}:run"

# Override CMD ["all"] → ["ibge-pam"]; ENTRYPOINT ["embrapa","ingest"] stays, so
# the container runs `embrapa ingest ibge-pam` (delta-aware, keyless).
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" <<JSON
{"overrides":{"containerOverrides":[{"args":["ibge-pam"]}],"timeout":"${TASK_TIMEOUT}","taskCount":1}}
JSON

if gcloud scheduler jobs describe "$SCHED_NAME" \
     --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

echo "${ACTION^} scheduler '$SCHED_NAME': '$CRON' ($SCHED_TZ) → run '$JOB_NAME' as ibge-pam (timeout ${TASK_TIMEOUT})"
gcloud scheduler jobs "$ACTION" http "$SCHED_NAME" --project "$PROJECT" --location "$REGION" \
  --schedule "$CRON" --time-zone "$SCHED_TZ" \
  --uri "$URI" --http-method POST \
  $( [ "$ACTION" = update ] && printf -- --update-headers || printf -- --headers ) "Content-Type=application/json" \
  --message-body-from-file "$BODY_FILE" \
  --oauth-service-account-email "$SCHED_SA"

cat <<EOF

Scheduled the MONTHLY IBGE PAM ingest. Before it can succeed, ensure (one-time):
  • the Job forwards PAM_* config — redeploy after this change:  make ingest-job-deploy
  • the scheduler SA can override args (same as reconcile/comtrade):
      gcloud run jobs add-iam-policy-binding $JOB_NAME --region $REGION --project $PROJECT \\
        --member "serviceAccount:$SCHED_SA" --role roles/run.jobsExecutorWithOverrides

Trigger a run now (delta — small):
  gcloud scheduler jobs run $SCHED_NAME --location $REGION --project $PROJECT
Or directly:
  gcloud run jobs execute $JOB_NAME --region $REGION --project $PROJECT --args=ibge-pam

For the one-time FULL historical backfill (1974→), run it locally against prod
(writes prod Bronze, like reconcile):  uv run embrapa ingest ibge-pam --full

NOTE: refreshes only BRONZE. Silver/Gold update on the next scheduled dbt build.
EOF
