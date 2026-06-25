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
# Image tag = explicit WEBAPI_TAG, else the current git SHA. Do NOT silently fall back
# to the mutable ':latest' when git can't resolve a SHA (non-git dir / detached shallow
# checkout): combined with WEBAPI_SKIP_BUILD that would deploy whatever ':latest' points
# at — which release.yml moves on every tag — instead of the intended revision (INFRA-3).
if [ -n "${WEBAPI_TAG:-}" ]; then
  TAG="$WEBAPI_TAG"
else
  TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
  [ -n "$TAG" ] || { echo "ERROR: cannot resolve a git SHA for the image tag and WEBAPI_TAG is unset; set WEBAPI_TAG explicitly (refusing to deploy the mutable ':latest')." >&2; exit 1; }
fi
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${SERVICE_NAME}:${TAG}"
MEMORY="${WEBAPI_MEMORY:-1Gi}"
CPU="${WEBAPI_CPU:-1}"
CONCURRENCY="${WEBAPI_CONCURRENCY:-16}"
# Keep min-instances=0 (scale to zero, ZERO idle cost — the zero-fixed-cost rule).
# A value >0 keeps warm instances billed 24/7; only set it on an explicit decision.
MIN_INSTANCES="${WEBAPI_MIN_INSTANCES:-0}"
MAX_INSTANCES="${WEBAPI_MAX_INSTANCES:-4}"
# Ingress. This service runs Cloud Run DIRECT IAP (run.googleapis.com/iap-enabled
# = true): IAP authenticates every request at the platform on the *.run.app URL
# and injects the trusted X-Goog-Authenticated-User-Email, so the SECURE posture
# here is `ingress=all` + IAP — NOT an ingress lock. This is FREE and scales to
# zero; an external HTTPS Load Balancer is a fixed monthly cost and is OUT OF SCOPE
# (future-only, see docs/auth_architecture.md + the zero-fixed-cost rule). Locking
# ingress to internal-and-cloud-load-balancing would BREAK direct IAP (it rejects
# the *.run.app path), so we DON'T force it: --ingress is passed only when the
# operator opts in (WEBAPI_INGRESS=...), reserved for that FUTURE external-HTTPS-LB
# + IAP topology. Unset (default) → Cloud Run preserves the service's current
# ingress, so a routine redeploy never changes the access path.
INGRESS="${WEBAPI_INGRESS:-}"

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

# 2) Build + push via Cloud Build (no local Docker required) — UNLESS deploying a
#    pre-built image. WEBAPI_SKIP_BUILD=1 skips the build and deploys ${IMAGE}
#    as-is, e.g. a release tag the CI already published (see
#    .github/workflows/release.yml): WEBAPI_SKIP_BUILD=1 WEBAPI_TAG=v1.2.3 deploy.sh.
#    Verify the image exists first so a wrong/absent tag fails loudly HERE rather
#    than erroring mid-deploy.
if [ -n "${WEBAPI_SKIP_BUILD:-}" ]; then
  echo "WEBAPI_SKIP_BUILD set — skipping Cloud Build; deploying pre-built image:"
  echo "  $IMAGE"
  if ! gcloud artifacts docker images describe "$IMAGE" --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: image not found in Artifact Registry: $IMAGE" >&2
    echo "       Publish it first (push a v* tag / run the 'Release image' workflow)," >&2
    echo "       or unset WEBAPI_SKIP_BUILD to build from source here." >&2
    exit 1
  fi
else
  echo "Building image via Cloud Build (node build + python)…"
  gcloud builds submit "$REPO_ROOT" --project "$PROJECT" \
    --config "$REPO_ROOT/deploy/webapi/cloudbuild.yaml" \
    --substitutions "_IMAGE=${IMAGE}"
fi

# 3) Runtime env from .env via an EXPLICIT ALLOWLIST (only what the webapi reads).
#    Runs AS the SA (ADC, no impersonation) → GCP_IMPERSONATION_SA NOT forwarded.
#    CURATION_DEV_AUTHOR is dev-only and omitted (prod identity comes from IAP).
#    SPA_DIST_DIR is baked into the image (not from .env).
#    BQ_GOLD_DATASET / BQ_SERVING_DATASET deliberately NOT forwarded — a dev .env
#    often points them at the auto-expiring dev datasets; forced to prod below.
#    CURATION_ALLOWED_EMAILS (the curation write lockdown) and BQ_MAX_BYTES_BILLED
#    (the serving-path cost ceiling) ARE forwarded — both are read by the deployed
#    webapi, and omitting them silently left prod on the open/default behaviour.
WEBAPI_ALLOWLIST='^(GCP_PROJECT_ID|BQ_LOCATION|CACHE_[A-Z0-9_]+|IAP_AUDIENCE|COMTRADE_BRAZIL_ISO|CURATION_ALLOWED_EMAILS|BQ_MAX_BYTES_BILLED|FEEDBACK_GITHUB_REPO)='
ENV_YAML="$(mktemp)"; trap 'rm -f "$ENV_YAML"' EXIT
grep -E "$WEBAPI_ALLOWLIST" "$ENV_FILE" \
  | while IFS='=' read -r key val; do
      printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')"
    done > "$ENV_YAML"

# 3a) Prod-only overrides (IAP_AUDIENCE, FEEDBACK_GITHUB_REPO, …): values that MUST
#     reach the prod service but deliberately do NOT live in a dev/worktree .env.
#     Without this, a routine deploy — which REPLACES the service env via
#     --env-vars-file — silently DROPS IAP_AUDIENCE (disarming the in-app IAP JWT
#     check in serving/iap.py AND the feedback cooldown that depends on it) and forces
#     an out-of-band / image-only deploy to restore it. A git-ignored prod file is
#     layered ON TOP of .env (same allowlist; prod values WIN). Override the path with
#     WEBAPI_PROD_ENV_FILE. Copy deploy/webapi/.env.prod.example → .env.prod to fill it.
PROD_ENV_FILE="${WEBAPI_PROD_ENV_FILE:-$REPO_ROOT/deploy/webapi/.env.prod}"
if [ -f "$PROD_ENV_FILE" ]; then
  echo "Applying prod env overrides from $PROD_ENV_FILE"
  { grep -E "$WEBAPI_ALLOWLIST" "$PROD_ENV_FILE" || true; } \
    | while IFS='=' read -r key val; do
        # Prod wins: drop any .env-derived line for this key, then append the prod value.
        { grep -v "^${key}:" "$ENV_YAML" || true; } > "${ENV_YAML}.new"
        mv "${ENV_YAML}.new" "$ENV_YAML"
        printf "%s: '%s'\n" "$key" "$(printf '%s' "$val" | tr -d '\r')" >> "$ENV_YAML"
      done
fi
printf "BQ_GOLD_DATASET: '%s'\n" "${WEBAPI_GOLD_DATASET:-gold}" >> "$ENV_YAML"
printf "BQ_SERVING_DATASET: '%s'\n" "${WEBAPI_SERVING_DATASET:-serving}" >> "$ENV_YAML"
grep -q '^GCP_PROJECT_ID:' "$ENV_YAML" || { echo "ERROR: GCP_PROJECT_ID missing in $ENV_FILE"; exit 1; }

# IAP_AUDIENCE arms the IN-APP IAP JWT verification (serving/iap.py) — a
# defense-in-depth double-check ON TOP of the platform's IAP enforcement. With
# Cloud Run direct IAP, IAP already authenticates every request and OVERWRITES the
# X-Goog-Authenticated-User-Email with the verified identity before it reaches the
# container, so curation `edited_by` is trustworthy even without the in-app check.
# IAP_AUDIENCE is therefore RECOMMENDED, not required — warn (don't fail) when it's
# absent so a routine redeploy isn't blocked, and set it to add the extra layer.
if ! grep -q '^IAP_AUDIENCE:' "$ENV_YAML"; then
  echo "NOTE: IAP_AUDIENCE not set — the in-app IAP JWT double-check (serving/iap.py)" >&2
  echo "      stays off. Cloud Run direct IAP still enforces auth + stamps the trusted" >&2
  echo "      user header, so this is acceptable. To keep the extra layer armed across" >&2
  echo "      routine deploys, set it in deploy/webapi/.env.prod (copy .env.prod.example)." >&2
fi

# 3b) Feedback GitHub loop (v1.6.0): mount the token secret so a routine redeploy does NOT
#     silently disable the loop (INFRA-1). FEEDBACK_GITHUB_REPO rides in via the allowlist
#     above; the token is a Secret Manager secret (never a plaintext env var), mounted only
#     when it exists — otherwise feedback degrades to BigQuery-only. Override the secret name
#     with FEEDBACK_GITHUB_TOKEN_SECRET.
FB_TOKEN_SECRET="${FEEDBACK_GITHUB_TOKEN_SECRET:-feedback-github-token}"
SECRET_FLAGS=()
if gcloud secrets describe "$FB_TOKEN_SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  SECRET_FLAGS=(--set-secrets "FEEDBACK_GITHUB_TOKEN=${FB_TOKEN_SECRET}:latest")
  echo "Feedback GitHub loop: mounting secret '${FB_TOKEN_SECRET}:latest'."
else
  echo "NOTE: secret '${FB_TOKEN_SECRET}' not found — feedback runs BigQuery-only (no GitHub loop)." >&2
fi

# 4) Deploy / update the Cloud Run Service (create-or-update), PRIVATE.
echo "Deploying Cloud Run Service…"
gcloud run deploy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$WEBAPI_SA" \
  --env-vars-file "$ENV_YAML" \
  ${SECRET_FLAGS[@]+"${SECRET_FLAGS[@]}"} \
  --no-allow-unauthenticated \
  ${INGRESS:+--ingress="$INGRESS"} \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --concurrency "$CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --port 8080

# 5) Enforce the invoker IAM check (--no-allow-unauthenticated alone is NOT enough;
#    the invoker-iam-disabled annotation can silently bypass IAM). Best-effort SET…
if ! gcloud run services update "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
      --invoker-iam-check >/dev/null 2>&1; then
  echo "WARNING: could not set --invoker-iam-check (gcloud may be too old)." >&2
  echo "         Upgrade gcloud and run: gcloud run services update $SERVICE_NAME --region $REGION --invoker-iam-check" >&2
fi

# 5b) …then VERIFY the end state and HARD-FAIL if IAM is bypassed. The best-effort
#     SET above can silently no-op (old gcloud, unwatched CI logs), so assert the
#     actual annotation: invoker-iam-disabled=true means IAM is bypassed even with
#     --no-allow-unauthenticated, leaving the service open to any authenticated
#     Google principal. Verifying the state (not just the SET) is what closes the gap.
IAM_DISABLED="$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
  --format='value(metadata.annotations."run.googleapis.com/invoker-iam-disabled")' 2>/dev/null || echo '')"
if [ "$IAM_DISABLED" = "true" ]; then
  echo "ERROR: run.googleapis.com/invoker-iam-disabled=true — invoker IAM is BYPASSED." >&2
  echo "       Fix: gcloud run services update $SERVICE_NAME --region $REGION --invoker-iam-check" >&2
  exit 1
fi

# 6) Sanity-check the service is NOT public.
if gcloud run services get-iam-policy "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
     --format='value(bindings.members)' 2>/dev/null | grep -Eq 'allUsers|allAuthenticatedUsers'; then
  echo "WARNING: an allUsers/allAuthenticatedUsers invoker binding is present — the service is PUBLIC." >&2
fi

# 6b) Assert Cloud Run DIRECT IAP is actually enabled — it is the trust anchor for
#     the whole auth model (it overwrites the spoofable plaintext user header with
#     the verified identity that `edited_by` records). A routine redeploy preserves
#     the annotation, but a freshly (re)created or renamed service could land
#     WITHOUT it and "succeed" while trusting a forgeable header. HARD-FAIL if it is
#     not on — UNLESS the operator opted into the future external-LB topology
#     (WEBAPI_INGRESS set), where IAP sits on the load balancer, not the service.
if [ -z "$INGRESS" ]; then
  IAP_ENABLED="$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT" --region "$REGION" \
    --format='value(metadata.annotations."run.googleapis.com/iap-enabled")' 2>/dev/null || echo '')"
  if [ "$IAP_ENABLED" != "true" ]; then
    echo "ERROR: run.googleapis.com/iap-enabled is not 'true' on $SERVICE_NAME — direct" >&2
    echo "       IAP is the trust anchor for curation author capture. Enable it:" >&2
    echo "       gcloud run services update $SERVICE_NAME --region $REGION --iap" >&2
    echo "       (or set WEBAPI_INGRESS for the external-LB + IAP topology.)" >&2
    exit 1
  fi
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
