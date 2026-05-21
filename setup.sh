#!/bin/bash
# Bootstrap script for macOS and Linux
# This script ensures Python is available before running setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS_NAME=$(uname -s)
PYTHON_CMD=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

find_python() {
    # Try Python 3.12+ first, then any Python 3.8+
    for cmd in python3.12 python3.11 python3.10 python3.9 python3.8 python3; do
        if command -v "$cmd" &> /dev/null; then
            # Verify it's Python 3.8+
            version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)

            if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done

    return 1
}

main() {
    print_header "Development Environment Setup - Bootstrap"

    echo "OS: $OS_NAME"
    echo "Script dir: $SCRIPT_DIR"
    echo ""

    # Step 1: Find Python
    print_info "Checking for Python 3.8+..."

    if PYTHON_CMD=$(find_python); then
        version=$("$PYTHON_CMD" --version)
        print_success "Found $version"
    else
        print_error "Python 3.8+ not found on this system"
        echo ""
        print_warning "Please install Python 3.8 or newer:"
        echo ""

        if [ "$OS_NAME" = "Darwin" ]; then
            echo "📦 macOS (with Homebrew):"
            echo "   brew install python@3.12"
            echo ""
            echo "📦 macOS (with MacPorts):"
            echo "   sudo port install python312"
            echo ""
        else
            echo "📦 Linux (Ubuntu/Debian):"
            echo "   sudo apt-get update"
            echo "   sudo apt-get install python3.12 python3.12-venv"
            echo ""
            echo "📦 Linux (Fedora):"
            echo "   sudo dnf install python3.12"
            echo ""
            echo "📦 Linux (Arch):"
            echo "   sudo pacman -S python"
            echo ""
        fi

        echo "Or download from: https://www.python.org/downloads/"
        echo ""
        exit 1
    fi

    # Step 2: Check uv
    print_info "Checking for uv..."
    if command -v uv &> /dev/null; then
        uv_version=$(uv --version)
        print_success "Found $uv_version"
    else
        print_error "uv not found"
        echo ""
        print_warning "Installing uv..."
        echo ""

        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Source the new PATH
        export PATH="$HOME/.local/bin:$PATH"

        if command -v uv &> /dev/null; then
            print_success "uv installed successfully"
        else
            print_error "Failed to install uv"
            echo "Try manual installation from: https://github.com/astral-sh/uv"
            exit 1
        fi
    fi

    # Step 3: Run setup script
    print_header "Running environment setup..."

    "$PYTHON_CMD" "$SCRIPT_DIR/scripts/setup_dev_env.py" "$@"
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        print_success "Bootstrap complete!"
    else
        print_error "Setup failed with exit code $exit_code"
    fi

    exit $exit_code
}

main "$@"
