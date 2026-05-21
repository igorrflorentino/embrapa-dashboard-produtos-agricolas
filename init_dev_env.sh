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

KEYFILE="$SCRIPT_DIR/.gcp-credentials.json"

# For Claude Code Web: decode GCP credentials from base64 env var if present.
# (No-op locally — devs don't set GCP_CREDENTIALS_B64 on their machines.)
if [ -n "${GCP_CREDENTIALS_B64:-}" ] && [ ! -f "$KEYFILE" ]; then
    echo "Decoding GCP_CREDENTIALS_B64 → $KEYFILE"
    echo "$GCP_CREDENTIALS_B64" | base64 -d > "$KEYFILE"
    chmod 600 "$KEYFILE"
fi

# Ensure uv is available (auto-install if missing)
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1090
    [ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"
    export PATH="$HOME/.local/bin:$PATH"
fi

# Pick whichever auth path is available (single source of truth)
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

# Materialize .env and ~/.dbt/profiles.yml on first run (Claude Code Web
# containers and other ephemeral sandboxes start with neither). On a dev
# machine where both already exist, skip the bootstrap to preserve any
# manual edits.
if [ ! -f "$SCRIPT_DIR/.env" ] || [ ! -f "$HOME/.dbt/profiles.yml" ]; then
    echo "Bootstrapping .env and dbt profile..."
    uv run python scripts/setup_dev_env.py
fi

# Run validation tests
uv run python scripts/test_setup.py

echo "✅ Environment ready!"
