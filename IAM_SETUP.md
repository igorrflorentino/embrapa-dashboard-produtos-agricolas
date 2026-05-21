# IAM Setup Guide

Step-by-step instructions for administrators to set up Google Cloud IAM roles and Service Accounts for the enterprise architecture.

## Prerequisites

- **Google Cloud Project:** `embrapa-dashboard-commodities`
- **gcloud CLI installed:** https://cloud.google.com/sdk/docs/install
- **Admin access** to the GCP project

## Overview

This guide creates:

1. **Four service accounts** with distinct responsibilities
2. **IAM role bindings** for developers and automation

No JSON keyfiles are generated, stored, or distributed. All access flows
through OAuth + service account impersonation.

**Estimated time:** 10-15 minutes

## Step 1: Authenticate as Admin

```bash
gcloud auth login your-admin@embrapa.com.br
gcloud config set project embrapa-dashboard-commodities
```

Verify:
```bash
gcloud config list
# Output:
# [core]
# project = embrapa-dashboard-commodities
```

## Step 2: Create Service Accounts

### 2.1 Developer Impersonation Target SA

```bash
gcloud iam service-accounts create sa-secret-reader-prod \
  --display-name="Developer Workflow (Prod)" \
  --description="Impersonation target for developer workflows (dbt + ad-hoc queries)."
```

Grant developer-workflow permissions:
```bash
# Read/write to BigQuery (dbt builds, ad-hoc queries)
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.dataEditor

# Run BigQuery jobs
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.jobUser

# Read GCS landing data
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/storage.objectViewer
```

> Note: the `sa-secret-reader-prod` name is historical — it pre-dates the
> decision to drop Secret Manager. The account is now purely an impersonation
> target. Feel free to rename it in your IAM console if you prefer.

### 2.2 Data Pipeline SA

```bash
gcloud iam service-accounts create sa-data-pipeline-prod \
  --display-name="Data Pipeline (Prod)" \
  --description="Runs IBGE and BCB ingestion pipelines. No human access."
```

Grant data pipeline permissions:
```bash
# Write to GCS (landing/)
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/storage.objectCreator

# Write to BigQuery (Bronze)
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.dataEditor

# Run BigQuery jobs
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.jobUser
```

### 2.3 Web Dashboard SA

```bash
gcloud iam service-accounts create sa-web-dashboard-prod \
  --display-name="Web Dashboard (Prod)" \
  --description="Read-only access for Looker Studio and web apps."
```

Grant read-only access:
```bash
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-web-dashboard-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.dataViewer
```

### 2.4 AI Agent Admin SA

```bash
gcloud iam service-accounts create sa-ai-agent-admin-prod \
  --display-name="AI Agent Admin (Prod)" \
  --description="AI agents for analysis, reporting. Subject to quotas."
```

Grant analytics permissions:
```bash
# Read and analyze data
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-ai-agent-admin-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/bigquery.dataEditor

# Read from GCS
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-ai-agent-admin-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/storage.objectViewer

# Write reports to GCS
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-ai-agent-admin-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/storage.objectCreator
```

### 2.5 Verify Service Accounts Created

```bash
gcloud iam service-accounts list --filter="displayName:*Prod"

# Output:
# NAME                                             EMAIL
# sa-secret-reader-prod                           sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
# sa-data-pipeline-prod                           sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
# sa-web-dashboard-prod                           sa-web-dashboard-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
# sa-ai-agent-admin-prod                          sa-ai-agent-admin-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
```

## Step 3: Grant Developer Impersonation Access

Developers need permission to impersonate `sa-secret-reader-prod` so dbt and
ad-hoc queries can run as that service account.

### 3.1 For Individual Developer

```bash
# Replace with actual email
DEVELOPER_EMAIL="developer@embrapa.com.br"

gcloud iam service-accounts add-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:${DEVELOPER_EMAIL} \
  --role=roles/iam.serviceAccountTokenCreator
```

### 3.2 For Development Team (Batch)

```bash
# Create batch_developers.txt with one email per line
cat > batch_developers.txt << 'EOF'
dev1@embrapa.com.br
dev2@embrapa.com.br
dev3@embrapa.com.br
EOF

# Grant all at once
while read email; do
  gcloud iam service-accounts add-iam-policy-binding \
    sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
    --member=user:${email} \
    --role=roles/iam.serviceAccountTokenCreator
done < batch_developers.txt
```

### 3.3 Verify Developer Permissions

```bash
gcloud iam service-accounts get-iam-policy \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --format=json | jq '.bindings[] | select(.role=="roles/iam.serviceAccountTokenCreator")'

# Output:
# {
#   "role": "roles/iam.serviceAccountTokenCreator",
#   "members": [
#     "user:dev1@embrapa.com.br",
#     "user:dev2@embrapa.com.br"
#   ]
# }
```

## Step 4: Authenticate Developers

Each developer runs this **once per machine** (or after gcloud is installed):

```bash
# Developer command
gcloud auth application-default login

# Or for specific account
gcloud auth login developer@embrapa.com.br
```

This opens a browser, developer logs in with their Google account, and an OAuth token is cached locally.

## Step 5: Developer Setup

Each developer runs the setup script:

```bash
# Developer command
cd embrapa-dashboard-commodities
python3 setup_dev_env.py
```

The script will:
1. Detect OAuth context (gcloud auth)
2. Validate impersonation permissions
3. Create `.env` with `GCP_AUTH_METHOD=impersonation`
4. Create `dbt/profiles.yml` with `method: oauth` + `impersonate_service_account`

## Step 6: Verify Setup

### 6.1 Developer Verifies Setup

```bash
# Developer runs:
uv run embrapa doctor

# Output should include:
# ✅ BigQuery connection: OK (impersonating sa-secret-reader-prod)
# ✅ GCS bucket access: OK
# ✅ dbt: OK (using OAuth)
```

### 6.2 Admin Checks Audit Logs

```bash
# Admin verifies audit trail
gcloud logging read \
  "protoPayload.authenticationInfo.principalEmail=developer@embrapa.com.br AND
   protoPayload.request.policy.bindings.members=*sa-secret-reader-prod*" \
  --limit=10 \
  --format=table(timestamp,protoPayload.methodName,protoPayload.authenticationInfo.principalEmail)

# Output shows impersonation events:
# 2026-05-21T15:30:45.123Z  compute.instances.setServiceAccount  developer@embrapa.com.br
```

## Step 7 (Optional): Grant Additional Service Account Roles

### For CI/CD (Cloud Run / Cloud Scheduler)

If you want automated pipelines to run as `sa-data-pipeline-prod`:

```bash
# Service: Cloud Run Jobs
gcloud iam service-accounts add-iam-policy-binding \
  sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=serviceAccount:cloud-run-service-account@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser
```

### For GitHub Actions Workload Identity Federation (No Secret Keys in GitHub)

```bash
# Create GitHub OIDC provider (one-time setup)
gcloud iam workload-identity-pools create "github-pool" \
  --project="embrapa-dashboard-commodities" \
  --location="global" \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="embrapa-dashboard-commodities" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.aud=assertion.aud,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Bind GitHub to sa-data-pipeline-prod
gcloud iam service-accounts add-iam-policy-binding \
  sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --project="embrapa-dashboard-commodities" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/NUMERIC_PROJECT_ID/locations/global/workloadIdentityPools/github-pool/attribute.repository/igorrflorentino/embrapa-dashboard-commodities"
```

## Step 8: Credential Rotation

There is nothing to rotate manually. OAuth tokens are short-lived (~1 hour)
and refreshed automatically by gcloud. No static service account keys exist
in this architecture.

## Step 9: Offboarding (Revoke Developer Access)

When a developer leaves:

```bash
DEPARTING_EMAIL="departing@embrapa.com.br"

# Remove impersonation permission
gcloud iam service-accounts remove-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:${DEPARTING_EMAIL} \
  --role=roles/iam.serviceAccountTokenCreator

# Immediate effect - no new tokens can be generated
# No need to rotate the service account key
```

Verify removal:
```bash
gcloud iam service-accounts get-iam-policy \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --format=json | jq '.bindings[] | select(.role=="roles/iam.serviceAccountTokenCreator") | .members'

# Output should NOT include the departing email
```

## Troubleshooting

### "Permission denied: cannot impersonate sa-secret-reader-prod"

**Problem:** Developer's account is missing the Token Creator role.

**Solution:** Verify developer is in `iam.serviceAccountTokenCreator` role:
```bash
gcloud iam service-accounts get-iam-policy \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
```

If missing, re-run Step 3 for that developer.

### "Failed to impersonate: Invalid Compute Credential"

**Problem:** gcloud auth not working.

**Solution:**
```bash
gcloud auth application-default login
# or
gcloud auth login developer@embrapa.com.br
```

### "Service account sa-secret-reader-prod does not exist"

**Problem:** Service account not created.

**Solution:** Run Step 2.1 to create it.

### "embrapa doctor: BigQuery connection failed"

**Problem:** Setup script detected impersonation, but it doesn't actually work.

**Solution:**
1. Verify `gcloud auth` is configured:
   ```bash
   gcloud config list
   ```
2. Verify developer has impersonation permission (Step 3)
3. Check audit logs for permission errors:
   ```bash
   gcloud logging read "resource.type=service_account" --limit=10
   ```

## Reference: Complete IAM Permission Matrix

| Component | Service Account | Roles | Purpose |
|---|---|---|---|
| **Developer Local** | (user email) | `roles/iam.serviceAccountTokenCreator` on `sa-secret-reader-prod` | Can impersonate developer workflow SA |
| **Developer Workflow** | `sa-secret-reader-prod` | `roles/bigquery.dataEditor`<br/>`roles/bigquery.jobUser`<br/>`roles/storage.objectViewer` | dbt builds + ad-hoc queries |
| **Data Pipeline** | `sa-data-pipeline-prod` | `roles/storage.objectCreator`<br/>`roles/bigquery.dataEditor`<br/>`roles/bigquery.jobUser` | IBGE/BCB ingestion |
| **Web Dashboard** | `sa-web-dashboard-prod` | `roles/bigquery.dataViewer` | Looker Studio read-only |
| **AI Agent Admin** | `sa-ai-agent-admin-prod` | `roles/bigquery.dataEditor`<br/>`roles/storage.objectViewer`<br/>`roles/storage.objectCreator` | Data analysis + reporting |

## Common Commands

### List all service accounts
```bash
gcloud iam service-accounts list
```

### View service account details
```bash
gcloud iam service-accounts describe sa-data-pipeline-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
```

### List all IAM roles on a project
```bash
gcloud projects get-iam-policy embrapa-dashboard-commodities --flatten="bindings[].members" --format=table
```

### Check specific member's roles
```bash
gcloud projects get-iam-policy embrapa-dashboard-commodities \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:developer@embrapa.com.br" \
  --format=table(bindings.role)
```

### View recent audit logs
```bash
gcloud logging read "resource.type=gce_instance OR resource.type=bigquery_resource" \
  --limit=20 \
  --format=table(timestamp,protoPayload.methodName,protoPayload.authenticationInfo.principalEmail)
```

## Support

- **GCP Console:** https://console.cloud.google.com/iam-admin/serviceaccounts
- **Audit Logs:** https://console.cloud.google.com/logs
- **gcloud reference:** https://cloud.google.com/sdk/gcloud/reference/iam
- **IAM Roles:** https://cloud.google.com/iam/docs/understanding-roles

## Next Steps

1. **Admin:** Complete all steps in this guide
2. **Admin:** Share `setup_dev_env.py` and `ARCHITECTURE.md` with developers
3. **Developers:** Run `python3 setup_dev_env.py`
4. **Everyone:** Review audit logs quarterly
5. **Admin:** Rotate credentials quarterly (Step 10)
