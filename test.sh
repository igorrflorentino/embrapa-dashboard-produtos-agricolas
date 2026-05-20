#!/bin/bash
# Quick test script for development environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧪 Running environment tests..."
echo ""

python3 "$SCRIPT_DIR/test_setup.py" "$@"
