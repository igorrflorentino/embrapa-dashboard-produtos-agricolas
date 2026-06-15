#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Build + deploy the React SPA + Flask REST Cloud Run SERVICE (the Dash→React
# migration). Builds the 3-stage image (node build → python deps → runtime) and
# deploys it to the SAME service as the Dash app (default: embrapa-dashboard),
# same runtime SA, same PRIVATE+IAP posture — an in-place cutover. Researchers'
# URL + IAP grants keep working; only the served app changes.
#
# Reads config from the repo-root .env. Idempotent: re-running rebuilds + updates.
#
# Prereqs: gcloud authenticated; APIs run/cloudbuild/artifactregistry enabled;
# the runtime SA (sa-web-dashboard-prod) provisioned with READ serving+gold +
# project jobUser (make iam-grant). Same security posture as deploy/dashboard
# (see the cloud-run-auth memory): PRIVATE (--no-allow-unauthenticated) AND the
# invoker IAM check, both required. IAP direct on the service for browser SSO.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (copy .env.example → .env)"; exit 1; }

# Read a single .env value without sourcing; strip CR (Windows). `|| true`
# contains grep's no-match exit under set -euo pipefail.
get_env() { { grep -E "^$1=" "$ENV_FILE" || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

resolve_region() {
  local r="${WEBAPI_REGION:-}"
  if [ -z "$r" ]; then echo us-central1; return 0; fi
  case "$r" in
    US|us) echo us-central1 ;;
    EU|eu) echo europe-west1 ;;
    *-*)   echo "$r" ;;
    *) echo "ERROR: WEBAPI_REGION='$r' is not a Cloud Run region." >&2; exit 1 ;;
  esac
}

PROJECT="${GCP_PROJECT_ID:-$(get_env GCP_PROJECT_ID)}"
[ -n "$PROJECT" ] || { echo "ERROR: GCP_PROJECT_ID not set"; exit 1; }
REGION="$(WEBAPI_REGION="${WEBAPI_REGION:-$(get_env WEBAPI_REGION)}" resolve_region)"
# Default to the SAME service as the Dash app → in-place cutover.
SERVICE_NAME="${WEBAPI_SERVICE_NAME:-embrapa-dashboard}"
AR_REPO="${WEBAPI_AR_REPO:-embrapa-services}"
WEBAPI_SA="${WEBAPI_SA:-sa-web-dashboard-prod@${PROJECT}.iam.gserviceaccount.com}"
TAG="${WEBAPI_TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${SERVICE_NAME}:${TAG}"
MEMORY="${WEBAPI_MEMORY:-1Gi}"
CPU="${WEBAPI_CPU:-1}"
CONCURRENCY="${WEBAPI_CONCURRENCY:-16}"
MIN_INSTANCES="${WEBAPI_MIN_INSTANCES:-0}"
MAX_INSTANCES="${WEBAPI_MAX_INSTANCES:-4}"
# Ingress lock (docs/auth_architecture.md § Dashboard ingress — HARD REQUIREMENT):
# reject direct *.run.app traffic so the external HTTPS LB + IAP is the SOLE path
# and the X-Goog-Authenticated-User-Email header can't be client-forged. Override
# only for a deliberate non-IAP topology.
INGRESS="${WEBAPI_INGRESS:-internal-and-cloud-load-balancing}"

echo "Project=$PROJECT  Region=$REGION  Service=$SERVICE_NAME"
echo "Image=$IMAGE"
echo "Runtime SA=$WEBAPI_SA"

# 1) Artifact Registry repo (idempotent).
if ! gcloud artifacts repositories describe "$AR_REPO" \
      --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Creating Artifact Registry repo '$AR_REPO'…"
  gcloud artifacts repositories create "$AR_REPO" --repository-format docker \
    --location "$REGION" --project "$PROJECT" \
    --description "Embrapa Cloud Run service images"
fi

# 2) Build + push via Cloud Build (no local Docker required).
echo "Building image via Cloud Build (node build + python)…"
gcloud builds submit "$REPO_ROOT" --project "$PROJECT" \
  --config "$REPO_ROOT/deploy/webapi/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}"

# 3) Runtime env from .env via an EXPLICIT ALLOWLIST (only what the webapi reads).
#    Runs AS the SA (ADC, no impersonation) → GCP_IMPERSONATION_SA NOT forwarded.
#    CURATION_DEV_AUTHOR is dev-only and omitted (prod identity comes from IAP).
#    SPA_DIST_DIR is baked into the image (not from .env).
#    BQ_GOLD_DATASET / BQ_SERVING_DATASET deliberately NOT forwarded — a dev .env
#    often points them at the auto-expiring dev datasets; forced to prod below.
#    CURATION_ALLOWED_EMAILS (the curation write lockdown) and BQ_MAX_BYTES_BILLED
#    (the serving-path cost ceiling) ARE forwarded — both are read by the deployed
#    webapi, and omitting them silently left prod on the open/default behaviour.
WEBAPI_ALLOWLIST='^(GCP_PROJECT_ID|BQ_LOCATION|CACHE_[A-Z0-9_]+|IAP_AUDIENCE|COMTRADE_BRAZIL_ISO|CURATION_ALLOWED_EMAILS|BQ_MAX_BYTES_BILLED)='
ENV_YAML="$(mktemp)"; trap 'rm -f "$ENV_YAML"' EXIT
grep -E "$WEBAPI_ALLOWLIST" "$ENV_FILE" \
  | while IFS='=' read -r key val; do
      printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')"
    done > "$ENV_YAML"
printf "BQ_GOLD_DATASET: '%s'\n" "${WEBAPI_GOLD_DATASET:-gold}" >> "$ENV_YAML"
printf "BQ_SERVING_DATASET: '%s'\n" "${WEBAPI_SERVING_DATASET:-serving}" >> "$ENV_YAML"
grep -q '^GCP_PROJECT_ID:' "$ENV_YAML" || { echo "ERROR: GCP_PROJECT_ID missing in $ENV_FILE"; exit 1; }

# IAP_AUDIENCE arms the in-app IAP JWT verification (serving/iap.py). Without it
# the app falls back to trusting the PLAINTEXT X-Goog-Authenticated-User-Email
# header — so a deploy that also slipped its ingress lock would accept a FORGED
# curation author (`edited_by`). Refuse to deploy without it; override only for a
# deliberate pre-IAP bootstrap (which is then NOT safe for curation writes).
if ! grep -q '^IAP_AUDIENCE:' "$ENV_YAML"; then
  if [ "${ALLOW_NO_IAP_AUDIENCE:-0}" = "1" ]; then
    echo "WARNING: IAP_AUDIENCE unset — in-app IAP JWT check DISABLED; curation 'edited_by' is forgeable. Bootstrap-only." >&2
  else
    echo "ERROR: IAP_AUDIENCE missing in $ENV_FILE — required to verify the IAP JWT (docs/auth_architecture.md)." >&2
    echo "       Set IAP_AUDIENCE in .env, or re-run with ALLOW_NO_IAP_AUDIENCE=1 for a deliberate pre-IAP bootstrap." >&2
    exit 1
  fi
fi

# 4) Deploy / update the Cloud Run Service (create-or-update), PRIVATE.
echo "Deploying Cloud Run Service…"
gcloud run deploy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$WEBAPI_SA" \
  --env-vars-file "$ENV_YAML" \
  --no-allow-unauthenticated \
  --ingress "$INGRESS" \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --concurrency "$CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --port 8080

# 5) Enforce the invoker IAM check (--no-allow-unauthenticated alone is NOT enough;
#    the invoker-iam-disabled annotation can silently bypass IAM). Best-effort.
if ! gcloud run services update "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
      --invoker-iam-check >/dev/null 2>&1; then
  echo "WARNING: could not set --invoker-iam-check (gcloud may be too old)." >&2
  echo "         Upgrade gcloud and run: gcloud run services update $SERVICE_NAME --region $REGION --invoker-iam-check" >&2
fi

# 6) Sanity-check the service is NOT public.
if gcloud run services get-iam-policy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
     --format='value(bindings.members)' 2>/dev/null | grep -Eq 'allUsers|allAuthenticatedUsers'; then
  echo "WARNING: an allUsers/allAuthenticatedUsers invoker binding is present — the service is PUBLIC." >&2
fi

URL="$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
        --format='value(status.url)' 2>/dev/null || echo '<service-url>')"
cat <<EOF

Done. React SPA + REST API deployed PRIVATE to '$SERVICE_NAME' at:
  $URL

IAP (already configured on this service for the Dash app) gates browser SSO; the
served app is now the React SPA. Verify: open the URL (IAP login) → the dashboard
loads; /healthz returns {"status":"ok"} (app-level, OUTSIDE the /api blueprint —
/api/healthz would match the SPA catch-all and serve index.html with a misleading
200); the analytical charts are Plotly.
EOF
