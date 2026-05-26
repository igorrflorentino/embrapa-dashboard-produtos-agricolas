# Deploy the Dash dashboard to Cloud Run.
#
# Required env: GCP_PROJECT_ID (project that owns the gold dataset).
# Optional env:
#   DASH_SERVICE  -- Cloud Run service name (default: embrapa-dashboard-commodities)
#   DASH_REGION   -- Cloud Run region        (default: us-central1)
#   BQ_LOCATION   -- BigQuery location       (default: us-central1, matches gold dataset)
#   DASH_SA       -- runtime service account email. If unset, Cloud Run uses
#                    the project's default Compute Engine SA. For a dedicated
#                    least-privilege SA, run scripts\dashboard-setup-sa.ps1 first.

if (-not $env:GCP_PROJECT_ID) {
    Write-Host "GCP_PROJECT_ID is not set." -ForegroundColor Red
    Write-Host "  set with: `$env:GCP_PROJECT_ID = 'your-project-id'" -ForegroundColor DarkGray
    exit 1
}

$Service = if ($env:DASH_SERVICE) { $env:DASH_SERVICE } else { "embrapa-dashboard-commodities" }
$Region  = if ($env:DASH_REGION)  { $env:DASH_REGION }  else { "us-central1" }
$BqLoc   = if ($env:BQ_LOCATION)  { $env:BQ_LOCATION }  else { "us-central1" }

Write-Host "Deploying $Service to $Region (project $($env:GCP_PROJECT_ID))..." -ForegroundColor Cyan

$DeployArgs = @(
    "run", "deploy", $Service,
    "--source", ".",
    "--region", $Region,
    "--set-env-vars", "GCP_PROJECT_ID=$($env:GCP_PROJECT_ID),BQ_GOLD_DATASET=gold,BQ_LOCATION=$BqLoc,CLOUD_RUN_REGION=$Region",
    # Auth posture: private. Access is gated by roles/run.invoker -- see
    # docs/auth.md for how to grant a user or group. Do NOT switch to
    # --allow-unauthenticated without re-auditing what Gold exposes.
    "--no-allow-unauthenticated",
    "--memory", "1Gi",
    "--cpu", "1",
    "--min-instances", "0",
    "--max-instances", "5",
    "--port", "8080",
    "--cpu-boost"
)

if ($env:DASH_SA) {
    Write-Host "Runtime SA: $($env:DASH_SA)" -ForegroundColor DarkGray
    $DeployArgs += "--service-account"
    $DeployArgs += $env:DASH_SA
} else {
    Write-Host "Runtime SA: (Cloud Run default -- Compute Engine SA)" -ForegroundColor DarkGray
    Write-Host "  Tip: scripts\dashboard-setup-sa.ps1 provisions a dedicated read-only SA" -ForegroundColor DarkGray
}

gcloud @DeployArgs

if (-not $?) { exit 1 }

$Url = gcloud run services describe $Service --region $Region --format='value(status.url)'
Write-Host ""
Write-Host "Deployed to: $Url" -ForegroundColor Green
# Note: GFE reserves /healthz, so the app exposes its healthcheck at /_health.
Write-Host "Health check:" -ForegroundColor DarkGray
Write-Host "  curl -fsS $Url/_health" -ForegroundColor DarkGray

# -- Post-deploy smoke gate ------------------------------------------------
# Drive the live service's real HTTP surface (health, Dash bootstrap,
# callback graph, and a live BigQuery render) before declaring success.
Write-Host ""
Write-Host "Running post-deploy smoke against $Url ..." -ForegroundColor Cyan
uv run python scripts/dashboard_smoke.py --no-launch --url $Url
if (-not $?) {
    Write-Host ""
    Write-Host "Post-deploy smoke FAILED -- the new revision is serving but a check did not pass." -ForegroundColor Red
    Write-Host "  Heavier visual gate: scripts\dashboard-visual.ps1 --no-launch --url $Url" -ForegroundColor DarkGray
    exit 1
}
Write-Host "Post-deploy smoke passed." -ForegroundColor Green
Write-Host "  Optional visual gate before release: scripts\dashboard-visual.ps1 --no-launch --url $Url" -ForegroundColor DarkGray
