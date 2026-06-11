#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Create the Cloud Monitoring alert that fires when the nightly ingestion Cloud
# Run JOB has a FAILED execution — so a silent overnight failure pages someone
# instead of being noticed only when the dashboard looks stale.
#
# Two idempotent resources:
#   1. an email notification channel for INGEST_ALERT_EMAIL (reused if one we
#      previously created — tagged with a user-label — already exists);
#   2. an alert policy on run.googleapis.com/job/completed_execution_count with
#      result="failed" > 0 over a 1h window, scoped to the job, wired to (1).
#
# Run by the OPERATOR — it mutates prod Cloud Monitoring (gcloud). Defaults read
# from .env, mirroring deploy.sh / schedule.sh. The metric type, the gcloud
# command surface (channels = beta-only; policies = GA), and the AlertPolicy v3
# JSON were verified against the live Monitoring API + the gcloud reference.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found"; exit 1; }
get_env() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'; }

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }

JOB_NAME="${INGEST_JOB_NAME:-$(get_env INGEST_JOB_NAME)}"
JOB_NAME="${JOB_NAME:-embrapa-ingest-all}"

EMAIL="${INGEST_ALERT_EMAIL:-$(get_env INGEST_ALERT_EMAIL)}"
[ -n "$EMAIL" ] || {
  echo "ERROR: INGEST_ALERT_EMAIL not set — the alert recipient. Add it to .env:"
  echo "       INGEST_ALERT_EMAIL=ops@example.com"
  exit 1
}

CH_LABEL="embrapa_ingest_alert"   # user-label marking the channel we own (idempotency key)
CH_DISPLAY="${INGEST_ALERT_CHANNEL_NAME:-Embrapa ingestion alerts}"
POLICY_DISPLAY="Embrapa ingestion job failed - ${JOB_NAME}"   # must match alert_policy.json (post-substitution)
POLICY_TEMPLATE="$REPO_ROOT/deploy/ingestion/alert_policy.json"
[ -f "$POLICY_TEMPLATE" ] || { echo "ERROR: $POLICY_TEMPLATE not found"; exit 1; }

# ── 1. email notification channel(s) — one per recipient ──────────────────────
# INGEST_ALERT_EMAIL may be a COMMA-SEPARATED list; each address gets its own
# channel, reused on re-run by its email_address (idempotent), all attached to
# the policy below. `channels` is a beta-only surface (no GA command exists); we
# also tag ours with a user-label for ownership.
resolve_channel() {  # email -> channel resource name (find-or-create), logs to stderr
  local email="$1" ch
  ch="$(gcloud beta monitoring channels list --project "$PROJECT" \
        --filter="type=\"email\" AND labels.email_address=\"${email}\"" \
        --format='value(name)' 2>/dev/null | head -n1 || true)"
  if [ -z "$ch" ]; then
    echo "Creating email notification channel for ${email}" >&2
    ch="$(gcloud beta monitoring channels create --project "$PROJECT" \
          --display-name="$CH_DISPLAY" --type=email \
          --channel-labels="email_address=${email}" \
          --user-labels="${CH_LABEL}=1" --format='value(name)')"
  else
    echo "Reusing notification channel for ${email}: ${ch}" >&2
  fi
  echo "$ch"
}

CHANNELS=""
IFS=',' read -ra _EMAILS <<< "$EMAIL"
for _e in "${_EMAILS[@]}"; do
  _e="$(printf '%s' "$_e" | tr -d '[:space:]')" # trim any whitespace around commas
  [ -n "$_e" ] || continue
  _ch="$(resolve_channel "$_e")"
  [ -n "$_ch" ] || { echo "ERROR: could not resolve a channel for ${_e}"; exit 1; }
  CHANNELS="${CHANNELS:+$CHANNELS,}$_ch"
done
[ -n "$CHANNELS" ] || { echo "ERROR: no notification channels resolved from INGEST_ALERT_EMAIL"; exit 1; }

# ── 2. alert policy (GA; create if absent — never duplicate) ──────────────────
EXISTING="$(gcloud monitoring policies list --project "$PROJECT" \
  --filter="display_name=\"${POLICY_DISPLAY}\"" \
  --format='value(name)' 2>/dev/null | head -n1 || true)"

if [ -n "$EXISTING" ]; then
  cat <<EOF
Alert policy already exists: ${EXISTING}
Nothing to do. To recreate it (e.g. after editing alert_policy.json), delete it first:
  gcloud monitoring policies delete ${EXISTING} --project ${PROJECT}
EOF
  exit 0
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
sed -e "s/__JOB_NAME__/${JOB_NAME}/g" "$POLICY_TEMPLATE" > "$TMP"

echo "Creating alert policy '${POLICY_DISPLAY}'"
gcloud monitoring policies create --project "$PROJECT" \
  --policy-from-file="$TMP" \
  --notification-channels="$CHANNELS"

cat <<EOF

Alert ready. A FAILED execution of '${JOB_NAME}' now notifies ${EMAIL}.
Verify / inspect:
  gcloud monitoring policies list --project ${PROJECT} --filter='display_name="${POLICY_DISPLAY}"'
  gcloud beta monitoring channels list --project ${PROJECT} --filter='userLabels.${CH_LABEL}="1"'
EOF
