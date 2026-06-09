#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Build + deploy the dashboard Cloud Run SERVICE (long-lived HTTP, not a Job).
#
# Serves the Dash app (PEVS + trade + Multi-fonte) via gunicorn, reading the prod
# serving marts + gold reference tables on demand (Pushdown Computing). Reads
# config from the repo-root .env. Idempotent: re-running rebuilds the image and
# updates the service in place.
#
# Prereqs:
#   - gcloud authenticated; APIs enabled: run, cloudbuild, artifactregistry.
#   - The runtime SA exists with its least-privilege grants (READ serving + gold,
#     project jobUser). Provision it once with:  make iam-grant   (default SA:
#     sa-web-dashboard-prod). See docs/iam_setup.md / deploy/iam/.
#
# Security posture (see the cloud-run-auth memory + docs/iam_setup.md): the
# service is deployed PRIVATE (--no-allow-unauthenticated) AND with the invoker
# IAM check enforced — both are required, because the
# run.googleapis.com/invoker-iam-disabled annotation silently bypasses IAM even
# after --no-allow-unauthenticated. Browser SSO for end users is a documented
# follow-up (External HTTPS LB + IAP in front; the app already verifies the IAP
# JWT — see src/embrapa_commodities/serving/iap.py).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (copy .env.example → .env)"; exit 1; }

# Read a single value from .env without sourcing it (avoids bash interpreting odd
# values); strips a trailing CR so Windows CRLF files work too.
get_env() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'; }

# Resolve the Cloud Run region. Cloud Run requires a SINGLE region (e.g.
# us-central1) and rejects a BigQuery multi-region locator (US/EU). So
# DASHBOARD_REGION is a first-class input, decoupled from BQ_LOCATION, defaulting
# to us-central1; an explicit multi-region locator is mapped to a concrete region.
resolve_region() {
  local r="${DASHBOARD_REGION:-}"
  if [ -z "$r" ]; then echo us-central1; return 0; fi
  case "$r" in
    US|us) echo us-central1 ;;
    EU|eu) echo europe-west1 ;;
    *-*)   echo "$r" ;;
    *)
      echo "ERROR: DASHBOARD_REGION='$r' is not a Cloud Run region. Cloud Run needs a" >&2
      echo "       single region (e.g. us-central1, europe-west1), not a multi-region." >&2
      exit 1 ;;
  esac
}

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="$(DASHBOARD_REGION="${DASHBOARD_REGION:-$(get_env DASHBOARD_REGION)}" resolve_region)"
SERVICE_NAME="${DASHBOARD_SERVICE_NAME:-embrapa-dashboard}"
AR_REPO="${DASHBOARD_AR_REPO:-embrapa-services}"
DASHBOARD_SA="${DASHBOARD_SA:-sa-web-dashboard-prod@${PROJECT}.iam.gserviceaccount.com}"
TAG="${DASHBOARD_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${SERVICE_NAME}:${TAG}"
MEMORY="${DASHBOARD_MEMORY:-1Gi}"
CPU="${DASHBOARD_CPU:-1}"
CONCURRENCY="${DASHBOARD_CONCURRENCY:-8}"
MIN_INSTANCES="${DASHBOARD_MIN_INSTANCES:-0}"
MAX_INSTANCES="${DASHBOARD_MAX_INSTANCES:-4}"

echo "Project=$PROJECT  Region=$REGION  Service=$SERVICE_NAME"
echo "Image=$IMAGE"
echo "Runtime SA=$DASHBOARD_SA"

# 1) Artifact Registry repo (idempotent).
if ! gcloud artifacts repositories describe "$AR_REPO" \
      --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repo '$AR_REPO'…"
  gcloud artifacts repositories create "$AR_REPO" --repository-format docker \
    --location "$REGION" --project "$PROJECT" \
    --description "Embrapa Cloud Run service images"
fi

# 2) Build + push the image via Cloud Build (no local Docker required).
echo "Building image via Cloud Build…"
gcloud builds submit "$REPO_ROOT" --project "$PROJECT" \
  --config "$REPO_ROOT/deploy/dashboard/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}"

# 3) Build the Service env vars from .env via an EXPLICIT ALLOWLIST — forward ONLY
#    the keys the dashboard reads at runtime. The service runs AS the dashboard SA
#    (ADC, no impersonation), so GCP_IMPERSONATION_SA is intentionally NOT
#    forwarded (its presence would make the app try to impersonate another SA).
#    CURATION_DEV_AUTHOR is dev-only and omitted (production identity comes from
#    IAP). A YAML file handles values with commas/colons.
#
# Allowlist (anchored, prefix-based):
#   GCP_PROJECT_ID                          — project + BigQuery billing
#   BQ_LOCATION                             — query location
#   BQ_GOLD_DATASET / BQ_SERVING_DATASET    — gold reference tables + serving marts
#   CACHE_*                                 — flask-caching backend + TTLs
#   IAP_AUDIENCE                            — verify the signed IAP JWT (when behind IAP)
#   COMTRADE_BRAZIL_ISO                     — reporter filter for the cross-source reads
DASH_ALLOWLIST='^(GCP_PROJECT_ID|BQ_LOCATION|BQ_GOLD_DATASET|BQ_SERVING_DATASET|CACHE_[A-Z0-9_]+|IAP_AUDIENCE|COMTRADE_BRAZIL_ISO)='
ENV_YAML="$(mktemp)"; trap 'rm -f "$ENV_YAML"' EXIT
grep -E "$DASH_ALLOWLIST" "$ENV_FILE" \
  | while IFS='=' read -r key val; do
      printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')"
    done > "$ENV_YAML"
# GCP_PROJECT_ID is mandatory; everything else falls back to config.py defaults.
grep -q '^GCP_PROJECT_ID:' "$ENV_YAML" || { echo "ERROR: GCP_PROJECT_ID missing in $ENV_FILE"; exit 1; }

# 4) Deploy / update the Cloud Run Service (create-or-update), PRIVATE.
echo "Deploying Cloud Run Service…"
gcloud run deploy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$DASHBOARD_SA" \
  --env-vars-file "$ENV_YAML" \
  --no-allow-unauthenticated \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --concurrency "$CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --port 8080

# 5) Enforce the invoker IAM check. --no-allow-unauthenticated alone is NOT
#    enough: the invoker-iam-disabled annotation can silently bypass IAM. This
#    flag is newer than some gcloud builds, so apply it best-effort and warn if
#    the running gcloud lacks it (then upgrade gcloud and re-run this one line).
if ! gcloud run services update "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
      --invoker-iam-check >/dev/null 2>&1; then
  echo "WARNING: could not set --invoker-iam-check (gcloud may be too old)." >&2
  echo "         Upgrade gcloud and run:" >&2
  echo "         gcloud run services update $SERVICE_NAME --region $REGION --invoker-iam-check" >&2
fi

# 6) Sanity-check the service is NOT public (no allUsers / allAuthenticatedUsers
#    invoker binding). Warn loudly if it is — that would defeat the private posture.
if gcloud run services get-iam-policy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
     --format='value(bindings.members)' 2>/dev/null | grep -Eq 'allUsers|allAuthenticatedUsers'; then
  echo "WARNING: an allUsers/allAuthenticatedUsers invoker binding is present — the" >&2
  echo "         service is PUBLIC. Remove it: gcloud run services remove-iam-policy-binding" >&2
  echo "         $SERVICE_NAME --region $REGION --member=allUsers --role=roles/run.invoker" >&2
fi

URL="$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
        --format='value(status.url)' 2>/dev/null || echo '<service-url>')"
cat <<EOF

Done. Service '$SERVICE_NAME' deployed PRIVATE at:
  $URL

It is not publicly reachable. To use it:
  • As a developer (auth via your gcloud identity):
      gcloud run services proxy $SERVICE_NAME --region $REGION --project $PROJECT
      then open http://localhost:8080
  • Grant a specific person/group invoker access:
      gcloud run services add-iam-policy-binding $SERVICE_NAME --region $REGION \\
        --member='user:someone@example.com' --role=roles/run.invoker
  • For end-user browser SSO: front it with an External HTTPS LB + IAP (follow-up).
    Then set IAP_AUDIENCE in .env so the app verifies the signed IAP JWT.
EOF
