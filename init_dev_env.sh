#!/bin/bash
# Initialize development environment
# Supports both enterprise (OAuth/ADC) and legacy (keyfile) authentication
cd /home/user/embrapa-dashboard-commodities

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env" 2>/dev/null || true
fi

# Set up credentials — enterprise mode first, keyfile as fallback
KEYFILE="/home/user/embrapa-dashboard-commodities/.gcp-credentials.json"
if [ -f "$KEYFILE" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$KEYFILE"
    echo "🔑 Auth: legacy keyfile ($KEYFILE)"
else
    echo "🔒 Auth: enterprise mode (Application Default Credentials / OAuth)"
fi

# Install dependencies
uv sync

# Run tests
python3 test_setup.py

echo "✅ Environment ready!"
