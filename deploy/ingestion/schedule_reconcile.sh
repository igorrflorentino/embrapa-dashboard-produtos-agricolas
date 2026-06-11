#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Create/update the MONTHLY "deep-refresh" Cloud Scheduler trigger.
#
# The nightly trigger (schedule.sh) runs `embrapa ingest all` — DELTA: it only
# revisits a recent window per source, so an upstream CORRECTION to an OLD year
# (e.g. IBGE revising a 1999 PEVS value, or BCB re-publishing an old month) is
# never re-queried. This monthly trigger runs the SAME Job but overrides its
# args to `reconcile` (`embrapa ingest reconcile`), which ignores each source's
# delta/ETag short-circuit and re-fetches the WHOLE configured history — so
# old-year revisions land in Bronze. Silver's incremental model is year-agnostic
# (it re-scans whatever Bronze years got a newer ingestion_timestamp), so the
# scheduled dbt build then carries the correction all the way to Gold.
#
# WHY THE v2 API (not the v1 endpoint schedule.sh uses): overriding a Job's
# container args at run time requires the Cloud Run Admin **v2** `:run` method
# with an `overrides` body. The Knative-style v1 `:run` endpoint cannot override
# args. v2 overrides also let this monthly run get a longer task timeout than the
# nightly Job's default — the full window is heavier — without touching the Job.
#
# IAM: arg overrides require the **run.jobs.runWithOverrides** permission, which
# roles/run.invoker does NOT grant. The scheduler SA therefore needs
# roles/run.developer (or a custom role with run.jobs.runWithOverrides). That is
# an access-control change — the closing message prints the exact command for an
# operator to run; this script does not grant IAM itself.
#
# Run by the OPERATOR. Defaults read from .env, mirroring schedule.sh. Idempotent.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found"; exit 1; }
# `|| true` contains grep's no-match exit under set -euo pipefail — a var absent
# from .env is normal (it falls back to the default), not a script failure.
get_env() { { grep -E "^$1=" "$ENV_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

# Resolve the Cloud Run region exactly like schedule.sh (must match deploy.sh).
resolve_region() {
  local r="${INGEST_JOB_REGION:-}"
  if [ -z "$r" ]; then
    echo us-central1
    return 0
  fi
  case "$r" in
    US|us) echo us-central1 ;;
    EU|eu) echo europe-west1 ;;
    *-*)   echo "$r" ;;
    *)
      echo "ERROR: INGEST_JOB_REGION='$r' is not a Cloud Run region (multi-region not allowed)." >&2
      echo "       Set INGEST_JOB_REGION explicitly in .env (decoupled from BQ_LOCATION)." >&2
      exit 1
      ;;
  esac
}

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="$(INGEST_JOB_REGION="${INGEST_JOB_REGION:-$(get_env INGEST_JOB_REGION)}" resolve_region)"
JOB_NAME="${INGEST_JOB_NAME:-$(get_env INGEST_JOB_NAME)}"
JOB_NAME="${JOB_NAME:-embrapa-ingest-all}"

SCHED_NAME="${RECONCILE_SCHEDULE_NAME:-$(get_env RECONCILE_SCHEDULE_NAME)}"
SCHED_NAME="${SCHED_NAME:-${JOB_NAME}-reconcile-monthly}"
# Monthly, 1st of month at 03:00 — madrugada, two hours before the 05:00 nightly
# so the two never overlap (and a same-morning nightly delta on top of a fresh
# reconcile is just a no-op).
CRON="${RECONCILE_SCHEDULE_CRON:-$(get_env RECONCILE_SCHEDULE_CRON)}"
CRON="${CRON:-0 3 1 * *}"
SCHED_TZ="${RECONCILE_SCHEDULE_TZ:-$(get_env RECONCILE_SCHEDULE_TZ)}"
SCHED_TZ="${SCHED_TZ:-America/Sao_Paulo}"
SCHED_SA="${INGEST_SCHEDULE_SA:-$(get_env INGEST_SCHEDULE_SA)}"
SCHED_SA="${SCHED_SA:-sa-data-pipeline-prod@${PROJECT}.iam.gserviceaccount.com}"
# The full window is heavier than the delta — give the reconcile execution a
# longer task timeout than the nightly Job default (3600s). Configurable.
TASK_TIMEOUT="${RECONCILE_JOB_TASK_TIMEOUT:-$(get_env RECONCILE_JOB_TASK_TIMEOUT)}"
TASK_TIMEOUT="${TASK_TIMEOUT:-7200s}"

# Cloud Run Admin API **v2** "run job" endpoint — supports the overrides body.
URI="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB_NAME}:run"

# Override the container args (CMD) from the baked-in ["all"] to ["reconcile"];
# ENTRYPOINT stays ["embrapa","ingest"], so the container runs
# `embrapa ingest reconcile`. Bump the per-execution task timeout for the
# heavier full window.
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat > "$BODY_FILE" <<JSON
{"overrides":{"containerOverrides":[{"args":["reconcile"]}],"timeout":"${TASK_TIMEOUT}","taskCount":1}}
JSON

if gcloud scheduler jobs describe "$SCHED_NAME" \
     --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

echo "${ACTION^} scheduler '$SCHED_NAME': '$CRON' ($SCHED_TZ) → run '$JOB_NAME' as reconcile (timeout ${TASK_TIMEOUT})"
gcloud scheduler jobs "$ACTION" http "$SCHED_NAME" --project "$PROJECT" --location "$REGION" \
  --schedule "$CRON" --time-zone "$SCHED_TZ" \
  --uri "$URI" --http-method POST \
  --headers "Content-Type=application/json" \
  --message-body-from-file "$BODY_FILE" \
  --oauth-service-account-email "$SCHED_SA"

cat <<EOF

Scheduled the MONTHLY deep-refresh. Two one-time grants the scheduler SA needs
on this job (arg overrides require runWithOverrides, which run.invoker lacks):
  gcloud run jobs add-iam-policy-binding $JOB_NAME --region $REGION --project $PROJECT \\
    --member "serviceAccount:$SCHED_SA" --role roles/run.developer
  # (roles/run.developer includes run.jobs.runWithOverrides; run.invoker alone is not enough.)

Trigger a test run immediately (runs the FULL re-ingest — heavier than the nightly):
  gcloud scheduler jobs run $SCHED_NAME --location $REGION --project $PROJECT

Or run the deployed Job once on demand without the scheduler (same override):
  gcloud run jobs execute $JOB_NAME --region $REGION --project $PROJECT --args=reconcile

NOTE: this only refreshes BRONZE. Silver/Gold update on the next scheduled dbt
build (.github/workflows/dbt-build-prod.yml) — the incremental Silver is
year-agnostic, so a plain build carries the old-year revisions through to Gold.
EOF
