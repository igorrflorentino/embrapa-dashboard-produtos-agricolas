# Enterprise Cloud Architecture

Modern GCP authentication using **Service Account Impersonation** (OAuth) instead of sharing JSON keyfiles.

## Overview

This document describes the **Cadeia de Confiança** (Chain of Trust) security model that eliminates JSON credential files from developer machines while maintaining secure, auditable access to GCP resources.

## The Problem with JSON Keyfiles

Traditional setup required sharing service account JSON files:
- ❌ Files copied via email, Slack, Drive (multiple copies)
- ❌ Developers store files locally (risk of theft/exposure)
- ❌ No audit trail of who accessed what
- ❌ Revocation requires rotating credentials and re-distributing files
- ❌ Difficult to enforce least-privilege access

## The Solution: Service Account Impersonation

OAuth 2.0 with service account impersonation:
- ✅ No JSON keyfiles shared or stored locally
- ✅ Uses `gcloud auth` or browser login (ADC)
- ✅ Complete audit trail in GCP logs
- ✅ Instant revocation via IAM role removal
- ✅ Fine-grained permission control
- ✅ Automatic token refresh

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Developer Machine (Local)                                       │
│                                                                 │
│  ┌──────────────────────────────────────┐                      │
│  │ gcloud auth (Browser/OAuth)          │                      │
│  │ ↓                                    │                      │
│  │ .env (NO CREDENTIALS)                │                      │
│  │ dbt profiles.yml (OAuth method)      │                      │
│  │                                      │                      │
│  │ setup_dev_env_enterprise.py          │                      │
│  │ ↓ impersonate                        │                      │
│  │ sa-secret-reader-prod                │                      │
│  └────────────────────┬─────────────────┘                      │
│                       │                                         │
└───────────────────────┼─────────────────────────────────────────┘
                        │ OAuth 2.0
                        │ (Service Account Token Creator)
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ Google Cloud Project (embrapa-dashboard-commodities)           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Four-Tier Service Account Architecture                  │  │
│  │                                                         │  │
│  │ 1. sa-secret-reader-prod                               │  │
│  │    ├─ Has JSON keyfile (stored in Secret Manager)      │  │
│  │    ├─ Used ONLY by setup bootstrap process             │  │
│  │    ├─ Permission: secretmanager.secretAccessor         │  │
│  │    └─ Impersonated by developers for reading secrets   │  │
│  │                                                         │  │
│  │ 2. sa-data-pipeline-prod                               │  │
│  │    ├─ Runs ingestion pipelines (IBGE, BCB)            │  │
│  │    ├─ Impersonated by Cloud Run / Cloud Scheduler      │  │
│  │    ├─ Permissions:                                      │  │
│  │    │  - storage.objectCreator (write to GCS)           │  │
│  │    │  - bigquery.dataEditor (load to Bronze)           │  │
│  │    │  - bigquery.jobUser (execute jobs)                │  │
│  │    └─ NO human access                                  │  │
│  │                                                         │  │
│  │ 3. sa-web-dashboard-prod                               │  │
│  │    ├─ Looker Studio / Web App read access              │  │
│  │    ├─ Impersonated by web frontend                     │  │
│  │    ├─ Permissions: bigquery.dataViewer (read-only)     │  │
│  │    └─ NO write access to data                          │  │
│  │                                                         │  │
│  │ 4. sa-ai-agent-admin-prod                              │  │
│  │    ├─ AI agent administration (Claude, Vertex AI)      │  │
│  │    ├─ Impersonated by AI agents                        │  │
│  │    ├─ Permissions:                                      │  │
│  │    │  - bigquery.dataEditor (for analysis)             │  │
│  │    │  - storage.objectViewer (read GCS)                │  │
│  │    │  - storage.objectCreator (write reports)          │  │
│  │    └─ Subject to quota/rate limits                     │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Secret Manager                                          │  │
│  │                                                         │  │
│  │ Secret: embrapa-gcp-credentials                        │  │
│  │  ├─ Version 1: Initial key (JSON for sa-secret-reader) │  │
│  │  ├─ Version 2: Rotated key (quarterly)                 │  │
│  │  └─ Latest: Actively used                              │  │
│  │                                                         │  │
│  │ Access Control:                                         │  │
│  │  - Admins: secretmanager.secretAdmin                   │  │
│  │  - Developers: secretmanager.secretAccessor (via SA)   │  │
│  │  - Setup process: reads via sa-secret-reader-prod      │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Cadeia de Confiança (Chain of Trust)

The trust relationship flows downward:

```
                        Organization / Admin
                                ↓
                         (Trusts Service Accounts)
                                ↓
            sa-secret-reader-prod (has JSON key in Secret Manager)
                    ↙    ↓    ↘    ↖
                   /     |     \     \
                  /      |      \     \
         Developer   Cloud Run  Web App  AI Agent
        (impersonate via OAuth with Token Creator role)
```

**Key Principle:** The only account with a JSON keyfile is `sa-secret-reader-prod`, and it's protected in Secret Manager with minimal access. All other accounts are accessed via impersonation (OAuth), with audit trails for every operation.

## Authentication Flow

### Developer Setup

1. **Developer runs setup:**
   ```bash
   ./setup.sh  # or setup.bat on Windows
   python3 setup_dev_env_enterprise.py
   ```

2. **Script detects authentication context:**
   - Checks for gcloud CLI (installed via Cloud SDK)
   - Checks for Application Default Credentials (ADC) from browser login
   - Falls back to Secret Manager → Environment variable → Keyfile (legacy)

3. **If impersonation available:**
   - Script validates developer has `iam.serviceAccountTokenCreators` role on `sa-secret-reader-prod`
   - Generates OAuth token valid for ~1 hour
   - Updates dbt profiles to use `method: oauth` with `impersonate_service_account`
   - Sets `GCP_AUTH_METHOD=impersonation` in .env

4. **No JSON keyfile stored locally:**
   - Credentials flow through OAuth 2.0
   - Each API call includes short-lived token
   - Token auto-refreshes before expiration

### dbt Execution with Impersonation

```yaml
# ~/.dbt/profiles.yml (enterprise mode)
embrapa_commodities:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth                    # Modern: OAuth
      project: embrapa-dashboard-commodities
      impersonate_service_account: sa-secret-reader-prod@{project}.iam.gserviceaccount.com
      dataset: dbt_dev
      # ... rest of config
```

When dbt runs:
1. Reads OAuth token from gcloud's cached credentials
2. Uses token to call BigQuery APIs
3. BigQuery validates token has `iam.serviceAccountTokenCreators` on `sa-secret-reader-prod`
4. BigQuery executes query as if run by `sa-secret-reader-prod`
5. All actions logged to GCP audit logs with developer's identity + impersonated SA

### Python Client (Data Pipelines)

```python
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Impersonate sa-data-pipeline-prod
credentials = service_account.Credentials.from_service_account_info(
    info=secret_reader_creds,  # Only sa-secret-reader has JSON key
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
    target_principal=f"sa-data-pipeline-prod@{project}.iam.gserviceaccount.com",
)

# Use impersonated credentials for BigQuery/GCS
client = bigquery.Client(credentials=credentials, project=project)
```

## IAM Permission Structure

### Developer Role Assignment

**For service account impersonation to work, each developer must have:**

```
Project: embrapa-dashboard-commodities

Role on sa-secret-reader-prod:
  - roles/iam.serviceAccountTokenCreators
    (allows impersonation)

  - roles/iam.serviceAccountUser
    (required by some integrations)
```

**NOT needed anymore:**
- ❌ `roles/owner` or `roles/editor`
- ❌ `roles/bigquery.admin`
- ❌ Direct storage access
- ❌ JSON keyfile

### Service Account Role Assignments

| Service Account | Roles | Purpose |
|---|---|---|
| `sa-secret-reader-prod` | `roles/secretmanager.secretAccessor` | Read credentials from Secret Manager |
| `sa-data-pipeline-prod` | `roles/storage.objectCreator`<br/>`roles/bigquery.dataEditor`<br/>`roles/bigquery.jobUser` | Ingest data (IBGE, BCB) |
| `sa-web-dashboard-prod` | `roles/bigquery.dataViewer` | Looker Studio read-only access |
| `sa-ai-agent-admin-prod` | `roles/bigquery.dataEditor`<br/>`roles/storage.objectCreator` | Data analysis + report generation |

## Secret Manager Integration

### Admin: Create Secret

```bash
gcloud secrets create embrapa-gcp-credentials \
  --replication-policy=automatic \
  --data-file=service-account.json
```

### Admin: Grant Access

```bash
# Developer can read secret (via sa-secret-reader-prod)
gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
  --member=user:developer@embrapa.com.br \
  --role=roles/secretmanager.secretAccessor

# But only sa-secret-reader actually holds the key
gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
  --member=serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Setup Process: Read Secret

```bash
# setup_dev_env_enterprise.py runs:
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
response = client.access_secret_version(
    request={"name": "projects/PROJECT/secrets/embrapa-gcp-credentials/versions/latest"}
)
sa_key_json = response.payload.data.decode('UTF-8')

# Script reads secret, extracts project_id, then discards the JSON
# Nothing stored locally except .env (no credentials)
```

## Credential Rotation

### Quarterly Rotation (Admin Task)

```bash
# 1. Generate new service account key
gcloud iam service-accounts keys create new-key.json \
  --iam-account=sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com

# 2. Add new version to Secret Manager
gcloud secrets versions add embrapa-gcp-credentials \
  --data-file=new-key.json

# 3. Disable old version (optional)
gcloud secrets versions disable v1

# 4. Developers automatically use new version on next setup
./setup.sh
```

**No re-distribution needed.** Developers run setup once per quarter, and they automatically get the latest secret from Secret Manager.

## Audit & Compliance

### GCP Audit Logs

Every operation is logged with:
- **Who:** Developer's email (from OAuth token) + impersonated SA
- **What:** API call, resource modified, data read
- **When:** Timestamp with millisecond precision
- **Where:** Audit log entry with request/response details

```bash
# Query audit logs
gcloud logging read \
  "protoPayload.authenticationInfo.principalEmail=developer@embrapa.com.br OR 
   protoPayload.request.policy.bindings.members=sa-secret-reader-prod@..." \
  --limit=100 \
  --format=json
```

### Revocation

If a developer leaves:

```bash
# Remove their impersonation permission
gcloud iam service-accounts remove-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:departed@embrapa.com.br \
  --role=roles/iam.serviceAccountTokenCreators

# Immediate effect - no new credentials can be generated
# No need to rotate the keyfile itself
```

## Migration from Keyfile to Impersonation

### For Existing Setups

If you have `setup_dev_env.py` (old) or `.gcp-credentials.json`:

1. **Use new setup script:**
   ```bash
   python3 setup_dev_env_enterprise.py
   ```

2. **Script will:**
   - Detect impersonation context first (preferred)
   - Fall back to Secret Manager if impersonation unavailable
   - Fall back to keyfile (legacy) if needed
   - Update `.env` with `GCP_AUTH_METHOD` value
   - Update `dbt/profiles.yml` accordingly

3. **Existing keyfile remains:**
   - If fallback used, `.gcp-credentials.json` still created
   - Can be safely deleted once impersonation validated
   - Still in `.gitignore` (never committed)

### For New Developers

New developers should:

1. **Install gcloud CLI:**
   ```bash
   curl https://sdk.cloud.google.com | bash
   ```

2. **Authenticate:**
   ```bash
   gcloud auth application-default login
   # or
   gcloud auth login your-email@embrapa.com.br
   ```

3. **Run setup:**
   ```bash
   python3 setup_dev_env_enterprise.py
   ```

4. **Script uses impersonation automatically.**

## FAQ

**Q: Do I need a JSON keyfile?**
A: No. The enterprise setup uses OAuth via `gcloud auth` or browser login. If you have an existing keyfile, you can delete it (it's in .gitignore).

**Q: How does dbt authenticate?**
A: dbt uses the `oauth` method in `profiles.yml`. It reads a cached OAuth token from gcloud and uses it to call BigQuery, impersonating `sa-secret-reader-prod`.

**Q: What if gcloud CLI is not installed?**
A: The setup script will warn you. Install the Cloud SDK from https://cloud.google.com/sdk/docs/install. This is a one-time step per machine.

**Q: Can I use this with GitHub Actions / CI/CD?**
A: Yes. See `IAM_SETUP.md` for CI/CD integration using Workload Identity Federation (no service account keys in GitHub Secrets).

**Q: What if I lose my laptop?**
A: No problem. Your OAuth token is cached locally (in `~/.config/gcloud/` on Unix, `AppData\gcloud\` on Windows). Remove your IAM role on `sa-secret-reader-prod`, and that laptop can no longer access GCP.

**Q: Is this faster than keyfile auth?**
A: Slightly. OAuth tokens are cached, so subsequent API calls don't require a round-trip to get a token. Keyfile auth also caches, but the token generation step is implicit.

**Q: What's the audit trail like?**
A: Complete. Every BigQuery job, GCS object access, and Secret Manager read is logged with your identity + the impersonated service account. Admins can see exactly who did what and when.

## Related Documentation

- **IAM_SETUP.md** — Step-by-step IAM role and service account setup
- **setup_dev_env.py** — Original setup script (keyfile-based, for backward compatibility)
- **setup_dev_env_enterprise.py** — Modern setup script (OAuth with impersonation)
- **SETUP.md** — General setup documentation
- **SECRET_MANAGER.md** — Google Cloud Secret Manager guide
- **CLAUDE.md** — Project architecture and development commands

## Support

For questions or issues:
1. Check **IAM_SETUP.md** for permission configuration
2. Run `embrapa doctor` to diagnose authentication issues
3. Review GCP audit logs: https://console.cloud.google.com/logs
4. Contact your GCP administrator for IAM role assignments
