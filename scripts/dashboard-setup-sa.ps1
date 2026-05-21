# Provision a dedicated, least-privilege runtime service account for the
# Cloud Run dashboard. Idempotent — safe to re-run.
#
# Required env: GCP_PROJECT_ID
# Optional env:
#   DASH_SA_NAME    — SA short name (default: dashboard-runtime)
#   BQ_GOLD_DATASET — gold dataset name (default: gold)
#
# Grants:
#   roles/bigquery.dataViewer  on the gold dataset only
#   roles/bigquery.jobUser     at project level (required to run queries)

if (-not $env:GCP_PROJECT_ID) {
    Write-Host "GCP_PROJECT_ID is not set." -ForegroundColor Red
    Write-Host "  set with: `$env:GCP_PROJECT_ID = 'your-project-id'" -ForegroundColor DarkGray
    exit 1
}

$Project = $env:GCP_PROJECT_ID
$SaName  = if ($env:DASH_SA_NAME)    { $env:DASH_SA_NAME }    else { "dashboard-runtime" }
$Dataset = if ($env:BQ_GOLD_DATASET) { $env:BQ_GOLD_DATASET } else { "gold" }
$SaEmail = "$SaName@$Project.iam.gserviceaccount.com"

Write-Host "Project : $Project" -ForegroundColor DarkGray
Write-Host "SA      : $SaEmail" -ForegroundColor DarkGray
Write-Host "Dataset : $Dataset" -ForegroundColor DarkGray
Write-Host ""

# ── 1. Create the SA (idempotent) ─────────────────────────────────────────
$Existing = gcloud iam service-accounts list `
    --project=$Project `
    --filter="email:$SaEmail" `
    --format="value(email)" 2>$null

if ($Existing) {
    Write-Host "SA already exists: $SaEmail" -ForegroundColor DarkGray
} else {
    Write-Host "Creating SA $SaEmail..." -ForegroundColor Cyan
    gcloud iam service-accounts create $SaName `
        --project=$Project `
        --display-name="Embrapa Commodities Dashboard runtime" `
        --description="Read-only access to the gold BQ dataset for the public dashboard."
    if (-not $?) { exit 1 }
}

# ── 2. Grant dataViewer on the gold dataset ───────────────────────────────
Write-Host "Granting roles/bigquery.dataViewer on $Project`:$Dataset..." -ForegroundColor Cyan

# bq's dataset IAM grant needs a JSON access policy patch. Easiest is the
# `bq` mutation: get → modify → set. We use a single helper command per
# bq's supported flow.
$Tmp = New-TemporaryFile
try {
    bq show --format=prettyjson "$Project`:$Dataset" > $Tmp.FullName
    if (-not $?) {
        Write-Host "Failed to read dataset $Project`:$Dataset — does it exist?" -ForegroundColor Red
        exit 1
    }

    $Policy = Get-Content $Tmp.FullName | ConvertFrom-Json
    $Member = "serviceAccount:$SaEmail"
    $AlreadyGranted = $false
    foreach ($entry in $Policy.access) {
        if ($entry.role -eq "READER" -and $entry.userByEmail -eq $SaEmail) {
            $AlreadyGranted = $true; break
        }
    }
    if ($AlreadyGranted) {
        Write-Host "  (already a READER)" -ForegroundColor DarkGray
    } else {
        $Policy.access += [pscustomobject]@{ role = "READER"; userByEmail = $SaEmail }
        $Policy | ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 $Tmp.FullName
        bq update --source $Tmp.FullName "$Project`:$Dataset"
        if (-not $?) { exit 1 }
    }
} finally {
    Remove-Item $Tmp.FullName -ErrorAction SilentlyContinue
}

# ── 3. Grant jobUser at project level ─────────────────────────────────────
Write-Host "Granting roles/bigquery.jobUser at project level..." -ForegroundColor Cyan
gcloud projects add-iam-policy-binding $Project `
    --member="serviceAccount:$SaEmail" `
    --role="roles/bigquery.jobUser" `
    --condition=None `
    --quiet | Out-Null
if (-not $?) { exit 1 }

Write-Host ""
Write-Host "SA $SaEmail ready." -ForegroundColor Green
Write-Host "Use it in deploy:" -ForegroundColor DarkGray
Write-Host "  `$env:DASH_SA = '$SaEmail'" -ForegroundColor DarkGray
Write-Host "  scripts\dashboard-deploy.ps1" -ForegroundColor DarkGray
