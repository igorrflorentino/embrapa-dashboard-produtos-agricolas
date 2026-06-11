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
# `|| true` contains grep's no-match exit under set -euo pipefail — a var absent
# from .env is normal (it falls back to the default), not a script failure.
get_env() { { grep -E "^$1=" "$ENV_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

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
# the policy below. The notification-`channels` gcloud surface is BETA-only (and
# often not installed), so we hit the Monitoring REST API directly — that needs
# only base gcloud (for the token) + curl + python3. We tag ours with a
# user-label for ownership.
CH_API="https://monitoring.googleapis.com/v3/projects/${PROJECT}/notificationChannels"
TOKEN="$(gcloud auth print-access-token)"
[ -n "$TOKEN" ] || { echo "ERROR: could not get a gcloud access token"; exit 1; }

resolve_channel() {  # email -> channel resource name (find-or-create), logs to stderr
  local email="$1" existing
  existing="$(curl -fsS -G -H "Authorization: Bearer ${TOKEN}" \
        --data-urlencode "filter=type=\"email\" AND labels.email_address=\"${email}\"" \
        "$CH_API" 2>/dev/null \
        | python3 -c 'import sys,json; chs=json.load(sys.stdin).get("notificationChannels",[]); print(chs[0]["name"] if chs else "")' 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    echo "Reusing notification channel for ${email}: ${existing}" >&2
    echo "$existing"
    return 0
  fi
  echo "Creating email notification channel for ${email}" >&2
  curl -fsS -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    -d "{\"type\":\"email\",\"displayName\":\"${CH_DISPLAY}\",\"labels\":{\"email_address\":\"${email}\"},\"userLabels\":{\"${CH_LABEL}\":\"1\"}}" \
    "$CH_API" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("name","")) if not d.get("error") else sys.exit("channel create error: "+json.dumps(d["error"]))'
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

Alert ready. A FAILED execution of '${JOB_NAME}' now notifies: ${EMAIL}
Verify / inspect the policy:
  gcloud monitoring policies list --project ${PROJECT} --filter='display_name="${POLICY_DISPLAY}"'
EOF
