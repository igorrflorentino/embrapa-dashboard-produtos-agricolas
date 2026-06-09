#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Apply the dataset-scoped, LEAST-PRIVILEGE BigQuery/GCS IAM grants for the two
# service accounts the audit (PR #65) re-scoped away from project-wide access:
#
#   • Web Dashboard SA  — READ 'serving' + APPEND 'research_inputs' + project jobUser
#   • AI Agent Admin SA — project READ-ONLY + jobUser + WRITE confined to one sandbox
#
# Codifies docs/iam_setup.md §2.3 / §2.4. This is handoff-independent: it does NOT
# deploy the dashboard Service (that arrives with the design-system handoff) — it
# only provisions the SAs + their minimal grants so the eventual deploy is ready.
#
# IDEMPOTENT: re-running re-asserts the same access entries — it strips any prior
# (SA, role) dataset entry before re-adding, so it never appends duplicates (the
# runbook's bare `.access += [...]` would). Reads config from the repo-root .env.
#
# Usage:
#   make iam-grant              # apply the grants
#   DRY_RUN=1 make iam-grant    # print every change, touch nothing
#
# Prereqs: gcloud + bq + jq installed, authenticated as a project IAM admin. The
# 'serving' / 'research_inputs' datasets must already exist (auto-created on the
# first prod dbt build / first curation write) — the dashboard grants fail clearly
# if they don't.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (copy .env.example → .env)"; exit 1; }

# Read a single value from .env without sourcing it; strips a trailing CR.
get_env() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'; }

DRY_RUN="${DRY_RUN:-0}"

for tool in gcloud bq jq; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: '$tool' not found on PATH"; exit 1; }
done

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }

# Dataset names (mirror config.py defaults). BigQuery datasets use the BQ LOCATION
# (which legitimately may be a multi-region like US/EU) — NOT a Cloud Run region.
SERVING_DATASET="${BQ_SERVING_DATASET:-$(get_env BQ_SERVING_DATASET)}";          SERVING_DATASET="${SERVING_DATASET:-serving}"
RESEARCH_DATASET="${BQ_RESEARCH_INPUTS_DATASET:-$(get_env BQ_RESEARCH_INPUTS_DATASET)}"; RESEARCH_DATASET="${RESEARCH_DATASET:-research_inputs}"
BQ_LOCATION="${BQ_LOCATION:-$(get_env BQ_LOCATION)}";                            BQ_LOCATION="${BQ_LOCATION:-US}"

# Service accounts (override via env if your naming differs).
DASHBOARD_SA="${DASHBOARD_SA:-sa-web-dashboard-prod@${PROJECT}.iam.gserviceaccount.com}"
AI_AGENT_SA="${AI_AGENT_SA:-sa-ai-agent-admin-prod@${PROJECT}.iam.gserviceaccount.com}"
AGENT_SANDBOX_DATASET="${AGENT_SANDBOX_DATASET:-ai_reports}"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }

# Run a command, or just print it under DRY_RUN.
run() {
  if [ "$DRY_RUN" = "1" ]; then printf '   DRY-RUN: %s\n' "$*"; else "$@"; fi
}

# Project-level role binding. gcloud is idempotent (re-adding a binding is a no-op).
grant_project_role() {
  local sa="$1" role="$2"
  run gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${sa}" --role="$role" --condition=None --quiet
  [ "$DRY_RUN" = "1" ] || note "project ${role} → ${sa}"
}

# Dataset-scoped access (READER/WRITER/OWNER), applied to the dataset resource —
# never project-wide. Idempotent: drop any existing (SA, role) entry, then re-add.
grant_dataset_role() {
  local dataset="$1" role="$2" sa="$3"
  if ! bq show --format=prettyjson "${PROJECT}:${dataset}" >/dev/null 2>&1; then
    echo "ERROR: dataset ${PROJECT}:${dataset} not found — create it first" >&2
    echo "       (prod dbt build / first curation write), then re-run." >&2
    exit 1
  fi
  if [ "$DRY_RUN" = "1" ]; then
    printf '   DRY-RUN: grant %s on dataset %s to %s\n' "$role" "$dataset" "$sa"
    return 0
  fi
  local tmp_in tmp_out
  tmp_in="$(mktemp)"; tmp_out="$(mktemp)"
  bq show --format=prettyjson "${PROJECT}:${dataset}" > "$tmp_in"
  jq --arg sa "$sa" --arg role "$role" \
    '.access |= (map(select((.userByEmail // "") != $sa or .role != $role)) + [{role: $role, userByEmail: $sa}])' \
    "$tmp_in" > "$tmp_out"
  bq update --source "$tmp_out" "${PROJECT}:${dataset}" >/dev/null
  rm -f "$tmp_in" "$tmp_out"
  note "${role} on dataset ${dataset} → ${sa}"
}

ensure_sa() {
  local email="$1" display="$2" desc="$3"
  if gcloud iam service-accounts describe "$email" --project="$PROJECT" >/dev/null 2>&1; then
    note "SA exists: ${email}"
  else
    run gcloud iam service-accounts create "${email%%@*}" --project="$PROJECT" \
      --display-name="$display" --description="$desc"
  fi
}

ensure_dataset() {
  local dataset="$1"
  if bq show "${PROJECT}:${dataset}" >/dev/null 2>&1; then
    note "dataset exists: ${dataset}"
  else
    run bq mk --dataset --location="$BQ_LOCATION" "${PROJECT}:${dataset}"
  fi
}

say "Project ${PROJECT} · BQ location ${BQ_LOCATION} · DRY_RUN=${DRY_RUN}"

say "Web Dashboard SA — read '${SERVING_DATASET}', append '${RESEARCH_DATASET}', project jobUser"
ensure_sa "$DASHBOARD_SA" "Web Dashboard (Prod)" \
  "Stateless Cloud Run dashboard: read '${SERVING_DATASET}', append to '${RESEARCH_DATASET}'."
grant_dataset_role "$SERVING_DATASET"  READER "$DASHBOARD_SA"
grant_dataset_role "$RESEARCH_DATASET" WRITER "$DASHBOARD_SA"
grant_project_role "$DASHBOARD_SA" roles/bigquery.jobUser

say "AI Agent Admin SA — project read-only + jobUser, write confined to '${AGENT_SANDBOX_DATASET}'"
ensure_sa "$AI_AGENT_SA" "AI Agent Admin (Prod)" \
  "AI agents: read-only analysis; writes confined to one report sandbox."
ensure_dataset "$AGENT_SANDBOX_DATASET"
grant_project_role "$AI_AGENT_SA" roles/bigquery.dataViewer
grant_project_role "$AI_AGENT_SA" roles/bigquery.jobUser
grant_dataset_role "$AGENT_SANDBOX_DATASET" WRITER "$AI_AGENT_SA"
grant_project_role "$AI_AGENT_SA" roles/storage.objectViewer
grant_project_role "$AI_AGENT_SA" roles/storage.objectCreator

say "Done — least-privilege grants applied (idempotent)."
[ "$DRY_RUN" = "1" ] && note "(dry-run — nothing was changed)"
exit 0
