#!/bin/bash
# Setup Google Cloud service account for Claude Code Web development.
# Run this once per GCP project to create a limited-scope dev account.
#
# Usage:
#   bash scripts/setup-claude-code-web-sa.sh
#
# Output: JSON keyfile at scripts/sa-claude-code-web-dev-key.json
#         (Base64 encode and paste into Claude Code Web env vars)

set -e

PROJECT_ID="${GCP_PROJECT_ID:-embrapa-dashboard-commodities}"

echo "Setting up sa-claude-code-web-dev in project: $PROJECT_ID"
echo ""

# 1. Create service account
echo "[1/4] Creating service account..."
gcloud iam service-accounts create sa-claude-code-web-dev \
  --project="$PROJECT_ID" \
  --display-name="Claude Code Web Development" \
  --description="Limited-scope dev account for Claude Code Web sandbox (dbt_dev only, no prod access)"

SA_EMAIL="sa-claude-code-web-dev@${PROJECT_ID}.iam.gserviceaccount.com"
echo "✅ Created: $SA_EMAIL"
echo ""

# 2. Grant BigQuery read-only on all project data.
#    NOT dataEditor: a project-wide dataEditor would let this "dbt_dev only, no
#    prod access" SA WRITE/DELETE prod silver/gold — directly contradicting its
#    own scope, so a leaked key = full prod-data write. dataViewer is read-only
#    and lets the dev build read Bronze sources (and inspect prod for debugging)
#    without being able to mutate any dataset.
echo "[2/4] Granting BigQuery dataViewer (project read-only)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer" \
  --quiet

echo "✅ Granted BigQuery data viewer (read-only) role"
echo ""

# 3. Grant BigQuery user (run jobs + create datasets). The SA becomes OWNER of the
#    dbt_dev_* datasets it creates, so it has full read/write on its OWN dev
#    sandbox — but NO write to prod datasets it didn't create. This is the
#    dev-write path that replaces the project-wide dataEditor above (and it
#    subsumes jobUser, so no separate jobUser grant is needed).
echo "[3/4] Granting BigQuery user (jobs + own-dataset create/write)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.user" \
  --quiet

echo "✅ Granted BigQuery user role"
echo ""

# 4. Grant GCS read access to landing bucket
echo "[4/4] Granting GCS permissions (landing bucket read-only)..."
BUCKET="${PROJECT_ID}-datalake"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectViewer" \
  --quiet 2>/dev/null || true

echo "✅ Granted GCS read access"
echo ""

# 5. Create JSON keyfile
echo "Creating JSON keyfile..."
KEYFILE="scripts/sa-claude-code-web-dev-key.json"
gcloud iam service-accounts keys create "$KEYFILE" \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT_ID"

echo "✅ Keyfile created: $KEYFILE"
echo ""

# 6. Encode to base64
echo "Encoding to base64 for Claude Code Web env var..."
B64_CONTENT=$(base64 -w 0 < "$KEYFILE")
B64_FILE="scripts/sa-claude-code-web-dev-key.b64"
echo "$B64_CONTENT" > "$B64_FILE"

echo "✅ Base64 encoded: $B64_FILE"
echo ""

# 7. Instructions
echo "════════════════════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy the base64 content to Claude Code Web environment:"
echo "   cat $B64_FILE"
echo ""
echo "2. In Claude Code Web settings → 'Atualizar ambiente de nuvem':"
echo "   - Name: embrapa-dashboard-commodities"
echo "   - Network: Completo"
echo "   - Environment variables:"
echo "     GCP_PROJECT_ID=embrapa-dashboard-commodities"
echo "     GCP_CREDENTIALS_B64=<paste_content_here>"
echo ""
echo "3. Set the setup script to:"
echo "   #!/bin/bash"
echo "   ./init_dev_env.sh || true"
echo ""
echo "4. Open a Claude Code Web session — init_dev_env.sh will bootstrap"
echo "   .env + dbt profile and run scripts/test_setup.py automatically."
echo ""
echo "⚠️  Important:"
echo "   - Keep $KEYFILE and $B64_FILE secret (don't commit!)"
echo "   - If the key leaks, rotate it:"
echo "     gcloud iam service-accounts keys delete <KEY_ID> --iam-account=$SA_EMAIL"
echo "   - Then run this script again to create a new key"
echo ""
echo "════════════════════════════════════════════════════════════════"
