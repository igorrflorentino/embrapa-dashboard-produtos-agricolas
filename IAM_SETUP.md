# IAM Setup Guide

Step-by-step instructions for administrators to set up Google Cloud IAM roles and Service Accounts for the enterprise architecture.

## Prerequisites

- **Google Cloud Project:** `embrapa-dashboard-commodities`
- **gcloud CLI installed:** https://cloud.google.com/sdk/docs/install
- **Admin access** to the GCP project
- **Service account JSON keyfile** (for `sa-secret-reader-prod`)

## Overview

This guide creates:

1. **Four service accounts** with distinct responsibilities
2. **Secret Manager secret** to store credentials securely
3. **IAM role bindings** for developers and automation

**Estimated time:** 15-20 minutes

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

### 2.1 Secret Reader SA

```bash
gcloud iam service-accounts create sa-secret-reader-prod \
  --display-name="Secret Reader (Prod)" \
  --description="Reads credentials from Secret Manager. Only SA with JSON keyfile."
```

Grant Secret Manager access:
```bash
gcloud projects add-iam-policy-binding embrapa-dashboard-commodities \
  --member=serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

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

## Step 3: Create Service Account Key

**Important:** Only `sa-secret-reader-prod` has a JSON keyfile. Other accounts use impersonation.

```bash
# Create key for secret reader
gcloud iam service-accounts keys create sa-secret-reader-key.json \
  --iam-account=sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com

# Verify key created
ls -la sa-secret-reader-key.json
```

**Keep this file safe.** You'll use it to create the Secret Manager secret in the next step.

## Step 4: Create Secret Manager Secret

### 4.1 Enable Secret Manager API

```bash
gcloud services enable secretmanager.googleapis.com
```

### 4.2 Create Secret

```bash
gcloud secrets create embrapa-gcp-credentials \
  --replication-policy=automatic \
  --data-file=sa-secret-reader-key.json
```

Verify:
```bash
gcloud secrets describe embrapa-gcp-credentials
```

### 4.3 Verify Secret Access

```bash
gcloud secrets versions access latest --secret=embrapa-gcp-credentials | head -5

# Output (should show JSON):
# {
#   "type": "service_account",
#   "project_id": "embrapa-dashboard-commodities",
#   ...
```

### 4.4 Clean Up Local Key File

```bash
# Remove local copy (no longer needed)
rm sa-secret-reader-key.json

# Secret is safely stored in Secret Manager now
```

## Step 5: Grant Developer Impersonation Access

Developers need permission to impersonate `sa-secret-reader-prod` to read secrets.

### 5.1 For Individual Developer

```bash
# Replace with actual email
DEVELOPER_EMAIL="developer@embrapa.com.br"

gcloud iam service-accounts add-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:${DEVELOPER_EMAIL} \
  --role=roles/iam.serviceAccountTokenCreators
```

### 5.2 For Development Team (Batch)

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
    --role=roles/iam.serviceAccountTokenCreators
done < batch_developers.txt
```

### 5.3 Verify Developer Permissions

```bash
gcloud iam service-accounts get-iam-policy \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --format=json | jq '.bindings[] | select(.role=="roles/iam.serviceAccountTokenCreators")'

# Output:
# {
#   "role": "roles/iam.serviceAccountTokenCreators",
#   "members": [
#     "user:dev1@embrapa.com.br",
#     "user:dev2@embrapa.com.br"
#   ]
# }
```

## Step 6: Authenticate Developers

Each developer runs this **once per machine** (or after gcloud is installed):

```bash
# Developer command
gcloud auth application-default login

# Or for specific account
gcloud auth login developer@embrapa.com.br
```

This opens a browser, developer logs in with their Google account, and an OAuth token is cached locally.

## Step 7: Developer Setup

Each developer runs the enterprise setup script:

```bash
# Developer command
cd embrapa-dashboard-commodities
python3 setup_dev_env_enterprise.py
```

The script will:
1. Detect OAuth context (gcloud auth)
2. Validate impersonation permissions
3. Read credentials from Secret Manager via `sa-secret-reader-prod`
4. Create `.env` with `GCP_AUTH_METHOD=impersonation`
5. Create `dbt/profiles.yml` with OAuth method

## Step 8: Verify Setup

### 8.1 Developer Verifies Setup

```bash
# Developer runs:
uv run embrapa doctor

# Output should include:
# ✅ BigQuery connection: OK (impersonating sa-secret-reader-prod)
# ✅ GCS bucket access: OK
# ✅ dbt: OK (using OAuth)
```

### 8.2 Admin Checks Audit Logs

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

## Step 9 (Optional): Grant Additional Service Account Roles

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

## Step 10: Credential Rotation (Quarterly)

Every 90 days, rotate the `sa-secret-reader-prod` key:

```bash
# 1. Admin: Create new key
gcloud iam service-accounts keys create sa-secret-reader-key-v2.json \
  --iam-account=sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com

# 2. Admin: Add new version to Secret Manager
gcloud secrets versions add embrapa-gcp-credentials \
  --data-file=sa-secret-reader-key-v2.json

# 3. Admin: List versions (check new one is active)
gcloud secrets versions list embrapa-gcp-credentials

# 4. Admin: Optionally disable old version after 1 week
# gcloud secrets versions disable v1

# 5. Admin: Clean up local files
rm sa-secret-reader-key-v2.json

# 6. Developers: Next time they run setup, they automatically get new key
python3 setup_dev_env_enterprise.py
```

## Step 11: Offboarding (Revoke Developer Access)

When a developer leaves:

```bash
DEPARTING_EMAIL="departing@embrapa.com.br"

# Remove impersonation permission
gcloud iam service-accounts remove-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:${DEPARTING_EMAIL} \
  --role=roles/iam.serviceAccountTokenCreators

# Immediate effect - no new tokens can be generated
# No need to rotate the service account key
```

Verify removal:
```bash
gcloud iam service-accounts get-iam-policy \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --format=json | jq '.bindings[] | select(.role=="roles/iam.serviceAccountTokenCreators") | .members'

# Output should NOT include the departing email
```

## Troubleshooting

### "Permission denied: roles/secretmanager.secretAccessor"

**Problem:** Developer cannot read Secret Manager secret.

**Solution:**
1. Verify developer is in `iam.serviceAccountTokenCreators` role:
   ```bash
   gcloud iam service-accounts get-iam-policy \
     sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com
   ```
2. Verify `sa-secret-reader-prod` has `secretmanager.secretAccessor` role:
   ```bash
   gcloud projects get-iam-policy embrapa-dashboard-commodities \
     --flatten="bindings[].members" \
     --filter="bindings.role:secretmanager.secretAccessor"
   ```

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
2. Verify developer has impersonation permission (Step 5)
3. Check audit logs for permission errors:
   ```bash
   gcloud logging read "resource.type=service_account" --limit=10
   ```

## Reference: Complete IAM Permission Matrix

| Component | Service Account | Roles | Purpose |
|---|---|---|---|
| **Developer Local** | (user email) | `roles/iam.serviceAccountTokenCreators` on `sa-secret-reader-prod` | Can impersonate to read secrets |
| **Secret Manager** | `sa-secret-reader-prod` | `roles/secretmanager.secretAccessor` | Can read GCP credentials |
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
- **Secret Manager:** https://console.cloud.google.com/security/secret-manager
- **Audit Logs:** https://console.cloud.google.com/logs
- **gcloud reference:** https://cloud.google.com/sdk/gcloud/reference/iam
- **IAM Roles:** https://cloud.google.com/iam/docs/understanding-roles

## Next Steps

1. **Admin:** Complete all steps in this guide
2. **Admin:** Share `setup_dev_env_enterprise.py` and `ARCHITECTURE.md` with developers
3. **Developers:** Run `python3 setup_dev_env_enterprise.py`
4. **Everyone:** Review audit logs quarterly
5. **Admin:** Rotate credentials quarterly (Step 10)
