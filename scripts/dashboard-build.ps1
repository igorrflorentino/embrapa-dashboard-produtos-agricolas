# Build the Cloud Run container image locally.
# Tag is configurable via $env:DASH_IMAGE; default is embrapa-dashboard:local.
#
# This script is OPTIONAL — only useful if you want to test the image locally
# before deploying. `scripts\dashboard-deploy.ps1` builds in Cloud Build (no
# local Docker required), so you can skip this and go straight to deploy.

$Image = if ($env:DASH_IMAGE) { $env:DASH_IMAGE } else { "embrapa-dashboard:local" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed locally." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You have two options:" -ForegroundColor DarkGray
    Write-Host "  1. (Recommended) Skip the local build — run scripts\dashboard-deploy.ps1," -ForegroundColor DarkGray
    Write-Host "     which builds the image remotely via Cloud Build."                       -ForegroundColor DarkGray
    Write-Host "  2. Install Docker Desktop, then re-run this script."                        -ForegroundColor DarkGray
    exit 1
}

Write-Host "Building $Image from deploy/Dockerfile..." -ForegroundColor Cyan
docker build -f deploy/Dockerfile -t $Image .
if (-not $?) { exit 1 }

Write-Host ""
Write-Host "Built $Image" -ForegroundColor Green
Write-Host "Run locally with:" -ForegroundColor DarkGray
Write-Host "  docker run --rm -p 8080:8080 ``" -ForegroundColor DarkGray
Write-Host "    -v `"$env:APPDATA/gcloud:/home/app/.config/gcloud`" ``" -ForegroundColor DarkGray
Write-Host "    -e GCP_PROJECT_ID=`$env:GCP_PROJECT_ID ``" -ForegroundColor DarkGray
Write-Host "    $Image" -ForegroundColor DarkGray
