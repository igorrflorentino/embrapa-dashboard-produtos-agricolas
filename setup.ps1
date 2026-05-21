# Bootstrap script for Windows PowerShell
# This script ensures Python and uv are available before running setup
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1

param(
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Header {
    param([string]$Message)
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Blue
}

function Find-Python {
    # Try to find Python in PATH
    $pythonCmds = @('python3.12', 'python3.11', 'python3.10', 'python3.9', 'python3.8', 'python3', 'python')

    foreach ($cmd in $pythonCmds) {
        try {
            $version = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($version) {
                $major, $minor = $version.Split('.')
                if ([int]$major -ge 3 -and [int]$minor -ge 8) {
                    return $cmd
                }
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Install-Python {
    Write-Info "Attempting to install Python via Chocolatey..."

    # Check if Chocolatey is installed
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Warning-Custom "Chocolatey not found. Installing Chocolatey first..."

        # Install Chocolatey
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    }

    # Install Python
    Write-Info "Installing Python 3.12..."
    choco install python312 -y
}

function Install-Uv {
    Write-Info "Installing uv..."

    # Download and run uv installer
    $uvInstallerUrl = "https://astral.sh/uv/install.ps1"
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString($uvInstallerUrl))
}

function Main {
    Write-Header "Development Environment Setup - Bootstrap (Windows)"

    Write-Host "OS: Windows" -ForegroundColor White
    Write-Host "PowerShell: $($PSVersionTable.PSVersion)" -ForegroundColor White
    Write-Host ""

    # Step 1: Find Python
    Write-Info "Checking for Python 3.8+..."

    $pythonCmd = Find-Python
    if ($pythonCmd) {
        $version = & $pythonCmd --version
        Write-Success "Found $version"
    }
    else {
        Write-Error-Custom "Python 3.8+ not found"
        Write-Host ""
        Write-Warning-Custom "Python is required. Installing..."
        Write-Host ""

        try {
            Install-Python

            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

            $pythonCmd = Find-Python
            if ($pythonCmd) {
                Write-Success "Python installed successfully"
            }
            else {
                Write-Error-Custom "Failed to install Python"
                Write-Host ""
                Write-Host "Manual installation options:" -ForegroundColor Yellow
                Write-Host "1. Download from: https://www.python.org/downloads/"
                Write-Host "2. Or use Microsoft Store: 'python' app"
                Write-Host "3. Or use Chocolatey: choco install python312"
                Write-Host ""
                exit 1
            }
        }
        catch {
            Write-Error-Custom "Failed to install Python: $_"
            exit 1
        }
    }

    # Step 2: Check uv
    Write-Info "Checking for uv..."
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue

    if ($uvCmd) {
        $version = & uv --version
        Write-Success "Found $version"
    }
    else {
        Write-Error-Custom "uv not found"
        Write-Info "Installing uv..."

        try {
            Install-Uv

            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

            $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
            if ($uvCmd) {
                Write-Success "uv installed successfully"
            }
            else {
                Write-Error-Custom "Failed to install uv"
                Write-Host "Try manual installation: https://github.com/astral-sh/uv"
                exit 1
            }
        }
        catch {
            Write-Error-Custom "Failed to install uv: $_"
            exit 1
        }
    }

    # Step 3: Run setup script
    Write-Header "Running environment setup..."

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $setupPyPath = Join-Path $scriptDir "setup_dev_env.py"

    & $pythonCmd $setupPyPath @Args
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Success "Bootstrap complete!"
    }
    else {
        Write-Error-Custom "Setup failed with exit code $exitCode"
    }

    exit $exitCode
}

Main
