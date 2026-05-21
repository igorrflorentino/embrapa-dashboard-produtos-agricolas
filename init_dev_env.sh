#!/bin/bash
# Initialize development environment (auto-detects auth mode).
# Cross-platform safe: uses script-relative paths, no hardcoded absolutes.
#
# Use this as a SessionStart hook for Claude Code on the web, or as a
# quick-init script after `git clone` on any machine.
set -e

# Resolve the directory this script lives in (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# For Claude Code Web: decode GCP credentials from base64 env var if present
if [ -n "${GCP_CREDENTIALS_B64:-}" ]; then
    KEYFILE=".gcp-credentials.json"
    if [ ! -f "$KEYFILE" ]; then
        echo "Decoding GCP_CREDENTIALS_B64 → $KEYFILE"
        echo "$GCP_CREDENTIALS_B64" | base64 -d > "$KEYFILE"
        chmod 600 "$KEYFILE"
        export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/$KEYFILE"
    fi
fi

# Ensure uv is available (auto-install if missing)
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1090
    [ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"
    export PATH="$HOME/.local/bin:$PATH"
fi

# Configure credentials — pick whichever auth path is available
KEYFILE="$SCRIPT_DIR/.gcp-credentials.json"
if [ -f "$KEYFILE" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$KEYFILE"
    echo "🔑 Auth: legacy keyfile (${KEYFILE})"
elif [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "🔑 Auth: GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS}"
else
    echo "🔒 Auth: enterprise mode (Application Default Credentials / OAuth)"
fi

# Install dependencies
uv sync

# Run validation tests
python3 test_setup.py

echo "✅ Environment ready!"
