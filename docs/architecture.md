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
│  │ scripts/setup_dev_env.py             │                      │
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
│  │    ├─ Impersonation target for developers              │  │
│  │    ├─ No JSON keyfile distributed                      │  │
│  │    ├─ Used by dbt (BigQuery) and developer workflows   │  │
│  │    └─ Access granted via Token Creator role            │  │
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
└─────────────────────────────────────────────────────────────────┘
```

## Cadeia de Confiança (Chain of Trust)

The trust relationship flows downward:

```
                        Organization / Admin
                                ↓
                         (Trusts Service Accounts)
                                ↓
                  sa-secret-reader-prod (impersonation target)
                    ↙    ↓    ↘    ↖
                   /     |     \     \
                  /      |      \     \
         Developer   Cloud Run  Web App  AI Agent
        (impersonate via OAuth with Token Creator role)
```

**Key Principle:** No JSON keyfiles are distributed to developers. All identities are accessed via impersonation (OAuth) with audit trails for every operation. The `sa-secret-reader-prod` service account exists purely as an impersonation target for developer workflows (dbt, BigQuery queries).

## Authentication Flow

### Developer Setup

1. **Developer runs setup:**
   ```bash
   ./setup.sh  # or setup.bat on Windows
   python3 scripts/setup_dev_env.py
   ```

2. **Script detects authentication context:**
   - Checks for gcloud CLI (installed via Cloud SDK)
   - Checks for Application Default Credentials (ADC) from browser login
   - Falls back to GOOGLE_APPLICATION_CREDENTIALS env var → `--credentials-file` arg → manual JSON paste

3. **If impersonation available:**
   - Script validates developer has `iam.serviceAccountTokenCreator` role on `sa-secret-reader-prod`
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
3. BigQuery validates token has `iam.serviceAccountTokenCreator` on `sa-secret-reader-prod`
4. BigQuery executes query as if run by `sa-secret-reader-prod`
5. All actions logged to GCP audit logs with developer's identity + impersonated SA

### Python Client (Data Pipelines)

```python
from google.auth import default
from google.auth import impersonated_credentials

# Use developer OAuth (ADC) to impersonate sa-data-pipeline-prod
source_creds, _ = default()
credentials = impersonated_credentials.Credentials(
    source_credentials=source_creds,
    target_principal=f"sa-data-pipeline-prod@{project}.iam.gserviceaccount.com",
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
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
  - roles/iam.serviceAccountTokenCreator
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
| `sa-secret-reader-prod` | `roles/bigquery.dataEditor`<br/>`roles/bigquery.jobUser`<br/>`roles/storage.objectViewer` | Impersonation target for developers (dbt + ad-hoc queries) |
| `sa-data-pipeline-prod` | `roles/storage.objectCreator`<br/>`roles/bigquery.dataEditor`<br/>`roles/bigquery.jobUser` | Ingest data (IBGE, BCB) |
| `sa-web-dashboard-prod` | `roles/bigquery.dataViewer` | Looker Studio read-only access |
| `sa-ai-agent-admin-prod` | `roles/bigquery.dataEditor`<br/>`roles/storage.objectCreator` | Data analysis + report generation |

## Credential Management

**There are no long-lived JSON keyfiles in this architecture.** Developers
authenticate with their personal Google account (`gcloud auth
application-default login`) and impersonate `sa-secret-reader-prod` for
their daily work.

### Granting Access (Admin Task)

```bash
# Grant a new developer permission to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --member=user:new-developer@embrapa.com.br \
  --role=roles/iam.serviceAccountTokenCreator
```

The developer then runs `./setup.sh` and gets a working environment with no
credential file to manage.

### Rotation

Nothing to rotate manually — OAuth tokens are short-lived (~1 hour) and
refreshed automatically by gcloud. There is no static secret to expire.

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
  --role=roles/iam.serviceAccountTokenCreator

# Immediate effect - no new credentials can be generated
# No need to rotate the keyfile itself
```

## Migration from Keyfile to Impersonation

### For Existing Setups

If you have a pre-existing `.gcp-credentials.json`:

1. **Re-run the unified setup script:**
   ```bash
   python3 scripts/setup_dev_env.py
   ```

2. **Script will:**
   - Detect impersonation context first (preferred)
   - Fall back to GOOGLE_APPLICATION_CREDENTIALS env var if impersonation unavailable
   - Fall back to `--credentials-file` argument if provided
   - Fall back to manual JSON paste (legacy, last resort)
   - Update `.env` with `GCP_AUTH_METHOD` value
   - Update `~/.dbt/profiles.yml` accordingly

3. **Existing keyfile remains:**
   - Only used as a fallback when impersonation isn't available
   - Can be safely deleted once impersonation is validated
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
   python3 scripts/setup_dev_env.py
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
A: Yes. See `iam_setup.md` for CI/CD integration using Workload Identity Federation (no service account keys in GitHub Secrets).

**Q: What if I lose my laptop?**
A: No problem. Your OAuth token is cached locally (in `~/.config/gcloud/` on Unix, `AppData\gcloud\` on Windows). Remove your IAM role on `sa-secret-reader-prod`, and that laptop can no longer access GCP.

**Q: Is this faster than keyfile auth?**
A: Slightly. OAuth tokens are cached, so subsequent API calls don't require a round-trip to get a token. Keyfile auth also caches, but the token generation step is implicit.

**Q: What's the audit trail like?**
A: Complete. Every BigQuery job and GCS object access is logged with your identity + the impersonated service account. Admins can see exactly who did what and when.

## Related Documentation

- **iam_setup.md** — Step-by-step IAM role and service account setup
- **scripts/setup_dev_env.py** — Unified cross-platform setup script (auto-detects auth mode)
- **setup.md** — General setup documentation
- **CLAUDE.md** — Project architecture and development commands

## Support

For questions or issues:
1. Check **iam_setup.md** for permission configuration
2. Run `embrapa doctor` to diagnose authentication issues
3. Review GCP audit logs: https://console.cloud.google.com/logs
4. Contact your GCP administrator for IAM role assignments
