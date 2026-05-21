# Google Cloud Secret Manager Setup

Guide for using Google Cloud Secret Manager to manage GCP credentials securely.

## Overview

Instead of sharing credentials files, use Google Cloud Secret Manager to store and access credentials securely.

**Benefits:**
- ✅ No credentials files shared via email/Drive
- ✅ Centralized secret management
- ✅ Fine-grained access control (IAM)
- ✅ Complete audit logs
- ✅ Automatic secret rotation
- ✅ Instant revocation (no new files needed)

## Setup (One-Time by Admin)

### Step 1: Create Secret in Google Cloud Console

```bash
# Option A: Via Google Cloud Console
1. Go to: https://console.cloud.google.com/security/secret-manager
2. Click "Create Secret"
3. Name: embrapa-gcp-credentials
4. Replication: Automatic
5. Secret value: [paste your service-account.json content]
6. Click "Create Secret"
```

### Step 2: Create Secret via gcloud CLI

```bash
# Make sure you have gcloud CLI installed and authenticated
gcloud config set project embrapa-dashboard-commodities

# Create secret from file
gcloud secrets create embrapa-gcp-credentials \
  --replication-policy="automatic" \
  --data-file=service-account.json

# Output:
# Created secret [embrapa-gcp-credentials] with replication policy [automatic]
```

### Step 3: Grant Access to Developers

```bash
# Give developer read access to secret
gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
  --member=user:developer@embrapa.com.br \
  --role=roles/secretmanager.secretAccessor

# For a service account
gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
  --member=serviceAccount:dev-sa@embrapa-dashboard-commodities.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Step 4: Verify Access

```bash
# Test reading the secret (as dev)
gcloud secrets versions access latest --secret=embrapa-gcp-credentials

# Should output the service account JSON
```

## Usage (For Developers)

### Method 1: Automatic (Recommended)

Setup script automatically detects and uses Secret Manager:

```bash
# No special setup needed!
./setup.sh

# Script will:
# 1. Try Secret Manager (if you have GCP auth)
# 2. Fall back to env var or file if needed
# 3. Create .gcp-credentials.json locally
```

**Requirements:**
- GCP authentication available (Application Default Credentials)
- Your account has `secretmanager.secretAccessor` role
- `GCP_PROJECT_ID` environment variable set

### Method 2: Manual with Environment Variable

```bash
# Set project ID
export GCP_PROJECT_ID=embrapa-dashboard-commodities

# Run setup (will auto-detect Secret Manager)
./setup.sh
```

### Method 3: Using gcloud CLI

If you don't have Application Default Credentials:

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Or login with specific account
gcloud auth login your-email@embrapa.com.br

# Run setup
./setup.sh
```

## How It Works

### Without Secret Manager
```
Admin
  ↓
Shares JSON file (email/Drive/Slack)
  ↓
Dev downloads
  ↓
Risk: file shared multiple times
```

### With Secret Manager
```
Admin creates secret in GCP
  ↓
Dev runs setup
  ↓
Setup reads from Secret Manager (via API)
  ↓
Credential NEVER shared as file
  ↓
No risk, complete audit trail
```

## Setup Script Fallback Chain

When you run `./setup.sh`:

```
1. Try Secret Manager
   ├─ Check GCP_PROJECT_ID
   ├─ Check GCP authentication
   ├─ Read from Secret Manager
   └─ Success? ✅ Done!

2. Try Environment Variable
   ├─ Check GOOGLE_APPLICATION_CREDENTIALS
   ├─ Read from file
   └─ Success? ✅ Done!

3. Try --credentials-file argument
   ├─ Check --credentials-file /path/to/file
   ├─ Read from file
   └─ Success? ✅ Done!

4. Try Interactive Prompt
   ├─ Ask user to paste JSON
   └─ Parse JSON
```

## Troubleshooting

### "Secret Manager not available"

The secret doesn't exist or you don't have access.

**Solution:**
```bash
# Check if secret exists
gcloud secrets list

# Check your permissions
gcloud secrets get-iam-policy embrapa-gcp-credentials
```

### "Permission denied: Permission 'secretmanager.secrets.get' denied"

Your account doesn't have the required role.

**Solution:**
```bash
# Ask admin to grant access
# Admin runs:
gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
  --member=user:your-email@embrapa.com.br \
  --role=roles/secretmanager.secretAccessor
```

### "GCP_PROJECT_ID not set"

The script needs to know which project to use.

**Solution:**
```bash
# Set environment variable
export GCP_PROJECT_ID=embrapa-dashboard-commodities

# Or add to your shell profile
echo 'export GCP_PROJECT_ID=embrapa-dashboard-commodities' >> ~/.bashrc
```

### Application Default Credentials not found

You need to authenticate with Google Cloud.

**Solution:**
```bash
# Authenticate
gcloud auth application-default login

# Or login with specific account
gcloud auth login your-email@embrapa.com.br
```

## Secret Rotation

When you need to rotate credentials (quarterly recommended):

### Admin Rotates Secret

```bash
# Create new version of secret
gcloud secrets versions add embrapa-gcp-credentials \
  --data-file=new-service-account.json

# Disable old version (optional)
gcloud secrets versions disable v1
```

### Developers Automatically Use New Version

```bash
# Next time anyone runs setup:
./setup.sh

# They automatically get the latest secret version
# No need to redistribute files!
```

## Audit Log

View who accessed the secret and when:

```bash
# Check audit logs
gcloud logging read \
  "resource.type=secretmanager.googleapis.com/Secret AND \
   resource.labels.secret_id=embrapa-gcp-credentials" \
  --format=json \
  --limit=50
```

## Revocation

If a developer leaves or loses access:

```bash
# Remove their access immediately
gcloud secrets remove-iam-policy-binding embrapa-gcp-credentials \
  --member=user:departing-dev@embrapa.com.br \
  --role=roles/secretmanager.secretAccessor

# No need to rotate credentials (unless they copied the file)
```

## Security Best Practices

1. **Never share the secret content**
   - Use Secret Manager API
   - Don't copy/paste JSON to messages

2. **Use service accounts for CI/CD**
   ```bash
   # Create service account for CI
   gcloud iam service-accounts create github-actions --display-name="GitHub Actions"
   
   # Grant Secret Manager access
   gcloud secrets add-iam-policy-binding embrapa-gcp-credentials \
     --member=serviceAccount:github-actions@embrapa-dashboard-commodities.iam.gserviceaccount.com \
     --role=roles/secretmanager.secretAccessor
   ```

3. **Rotate regularly**
   - Every 90 days
   - After employee leaves
   - If credentials are compromised

4. **Monitor access**
   - Review audit logs monthly
   - Alert on unusual access patterns

5. **Least privilege**
   - Only grant `secretAccessor` role
   - Not `secretAdmin` or higher

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup environment
        env:
          GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
        run: |
          ./setup.sh
```

### GitLab CI Example

```yaml
# .gitlab-ci.yml
stages:
  - setup
  - build

setup:
  stage: setup
  script:
    - export GCP_PROJECT_ID=$GCP_PROJECT_ID
    - export GOOGLE_APPLICATION_CREDENTIALS=$GCP_SA_KEY
    - ./setup.sh
```

## FAQ

**Q: Can I use Secret Manager without gcloud CLI?**
A: Yes! If you have Application Default Credentials (logged in via Google Account), the setup script uses the API directly.

**Q: What if I don't have Secret Manager set up yet?**
A: The setup script falls back to other methods automatically. You can set it up later.

**Q: Can I use different secrets for different environments?**
A: Yes! Create separate secrets:
- `embrapa-gcp-credentials-dev`
- `embrapa-gcp-credentials-prod`

Then check which secret to use based on environment.

**Q: How long do secrets stay cached?**
A: The setup script reads fresh from Secret Manager every time. No caching in the script (only in your local `.gcp-credentials.json`).

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review SETUP.md for general setup issues
3. Check GCP documentation: https://cloud.google.com/secret-manager/docs
4. Contact your GCP admin
