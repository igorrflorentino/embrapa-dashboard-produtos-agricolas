# Deploy the Dash dashboard to Cloud Run.
#
# Required env: GCP_PROJECT_ID (project that owns the gold dataset).
# Optional env:
#   DASH_SERVICE  — Cloud Run service name (default: embrapa-commodities-dashboard)
#   DASH_REGION   — Cloud Run region        (default: us-central1)
#   BQ_LOCATION   — BigQuery location       (default: US)
#   DASH_SA       — runtime service account (default: dashboard-runtime@<project>)

if (-not $env:GCP_PROJECT_ID) {
    Write-Host "GCP_PROJECT_ID is not set." -ForegroundColor Red
    Write-Host "  set with: `$env:GCP_PROJECT_ID = 'your-project-id'" -ForegroundColor DarkGray
    exit 1
}

$Service = if ($env:DASH_SERVICE) { $env:DASH_SERVICE } else { "embrapa-commodities-dashboard" }
$Region  = if ($env:DASH_REGION)  { $env:DASH_REGION }  else { "us-central1" }
$BqLoc   = if ($env:BQ_LOCATION)  { $env:BQ_LOCATION }  else { "US" }
$Sa      = if ($env:DASH_SA)      { $env:DASH_SA }      else { "dashboard-runtime@$($env:GCP_PROJECT_ID).iam.gserviceaccount.com" }

Write-Host "Deploying $Service to $Region (project $($env:GCP_PROJECT_ID))..." -ForegroundColor Cyan
Write-Host "Runtime SA: $Sa" -ForegroundColor DarkGray

gcloud run deploy $Service `
    --source . `
    --region $Region `
    --service-account $Sa `
    --set-env-vars "GCP_PROJECT_ID=$($env:GCP_PROJECT_ID),BQ_GOLD_DATASET=gold,BQ_LOCATION=$BqLoc" `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 5 `
    --port 8080

if (-not $?) { exit 1 }

$Url = gcloud run services describe $Service --region $Region --format='value(status.url)'
Write-Host ""
Write-Host "Deployed to: $Url" -ForegroundColor Green
Write-Host "Health check:" -ForegroundColor DarkGray
Write-Host "  curl -fsS $Url/healthz" -ForegroundColor DarkGray
