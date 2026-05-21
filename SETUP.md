# Development Environment Setup

Automated cross-platform setup for the Embrapa Dashboard Commodities project. Works on fresh machines with no prior setup.

## Quick Start

### macOS / Linux

```bash
# Run setup (will auto-install Python and uv if needed)
./setup.sh
```

### Windows (Command Prompt)

```cmd
# Run setup (will auto-install Python and uv if needed)
setup.bat
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

## How It Works

The setup scripts are **fully bootstrapped** and handle fresh machines:

1. ✅ Detects OS (Windows/macOS/Linux)
2. ✅ Checks for Python 3.8+ (auto-installs if missing)
3. ✅ Checks for uv (auto-installs if missing)
4. ✅ **Auto-detects the best authentication mode** (enterprise OAuth/impersonation → Secret Manager → keyfile)
5. ✅ Creates `.env` file with configuration (records `GCP_AUTH_METHOD`)
6. ✅ Creates `~/.dbt/profiles.yml` matching the detected mode (OAuth+impersonation or keyfile)
7. ✅ Protects credentials in `.gitignore`
8. ✅ Validates entire setup with `embrapa doctor`

> **One script, two modes.** The same `setup_dev_env.py` produces an enterprise
> setup (OAuth + service-account impersonation, **no keyfile on disk**) when
> `gcloud auth application-default login` has been run, and falls back to the
> legacy JSON-keyfile flow otherwise. See [ARCHITECTURE.md](ARCHITECTURE.md)
> for the full enterprise model.

## Machine Requirements

### macOS / Linux
- **bash** — included by default
- **curl** — for downloading Python/uv (usually included)

### Windows
- **PowerShell 3.0+** — included in Windows 7+ (usually PowerShell 5+)
- **Internet connection** — for downloading Python and uv

**That's it!** No pre-installed tools required.

## Setup Scripts Overview

### `setup.sh` (macOS / Linux)
- Detects Python 3.8+ installations
- Auto-installs Python 3.12 via system package manager
- Auto-installs uv via curl
- Calls `setup_dev_env.py` for configuration

### `setup.bat` (Windows Command Prompt)
- Wrapper that calls `setup.ps1`
- No PowerShell knowledge needed

### `setup.ps1` (Windows PowerShell)
- Detects Python 3.8+ installations
- Auto-installs Python 3.12 via Chocolatey (or shows manual steps)
- Auto-installs uv via PowerShell
- Calls `setup_dev_env.py` for configuration

### `setup_dev_env.py` (Core Python Script)
- Cross-platform setup logic — single source of truth
- **Auto-detects** the best available authentication method
- Generates `.env` and `~/.dbt/profiles.yml` matching the detected mode
- Runs validation checks against the configured project

### `init_dev_env.sh` (One-shot init / SessionStart hook)
- Lightweight wrapper for already-cloned repos
- Used by Claude Code on the web and as a quick re-init
- Sets `GOOGLE_APPLICATION_CREDENTIALS` if a keyfile exists, otherwise lets
  Application Default Credentials take over
- Runs `uv sync` and `python3 test_setup.py`

## GCP Authentication Strategy

The setup script tries authentication strategies in this order, picking the
first one that works:

### 1️⃣ Service Account Impersonation (Enterprise — Recommended)

If you have run `gcloud auth application-default login` and your account has
`roles/iam.serviceAccountTokenCreator` on `sa-secret-reader-prod`, the script
configures **OAuth + impersonation**:

- ✅ No JSON keyfile written to disk
- ✅ Complete audit trail in Cloud Logging
- ✅ Instant revocation via IAM
- ✅ Automatic credential rotation (no re-distribution)

Generated `~/.dbt/profiles.yml` uses `method: oauth` with `impersonate_service_account`.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [IAM_SETUP.md](IAM_SETUP.md).

### 2️⃣ Google Cloud Secret Manager

If impersonation is not available but `GCP_PROJECT_ID` is set and you can
access the `embrapa-gcp-credentials` secret, the script reads the JSON
keyfile from Secret Manager:

```bash
export GCP_PROJECT_ID=embrapa-dashboard-commodities
./setup.sh
```

See [SECRET_MANAGER.md](SECRET_MANAGER.md) for setup details.

### 3️⃣ Environment Variable (legacy)

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
./setup.sh
```

### 4️⃣ File Argument (legacy)

```bash
./setup.sh --credentials-file /path/to/service-account.json
```

### 5️⃣ Interactive Prompt (last resort)

If none of the above work, the script prompts you to paste your service
account JSON. Avoid this path — copy/paste leaves traces.

## File Arguments

```bash
./setup.sh [OPTIONS]
  --credentials-file PATH    Path to GCP service account JSON file
  --help                     Show help message
```

Same options work with `setup.bat` and `setup.ps1`.

## Troubleshooting

### "Python not found"

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv
./setup.sh
```

#### Linux (Fedora)
```bash
sudo dnf install python3.12
./setup.sh
```

#### macOS
```bash
# Option 1: Homebrew
brew install python@3.12

# Option 2: MacPorts
sudo port install python312

# Option 3: Download from
# https://www.python.org/downloads/
```

#### Windows
The setup script (`setup.bat`) will offer to auto-install Python. If it fails:

```powershell
# Option 1: Chocolatey (auto-installer handles this)
choco install python312

# Option 2: Microsoft Store
# Search "Python" in Microsoft Store and install

# Option 3: Download from
# https://www.python.org/downloads/
```

### "uv installation failed"

The bootstrap scripts attempt auto-installation. If it fails:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then re-run setup:
```bash
./setup.sh    # or setup.bat on Windows
```

### "Invalid JSON" error

Make sure you're pasting a valid GCP service account JSON file. Obtain it from:
1. **Google Cloud Console** → **Service Accounts** → Your account → **Keys** → **Add Key** → **JSON**

### "GCS bucket access denied (403)"

This may happen if the service account doesn't have proper IAM roles:

1. **Google Cloud Console** → **IAM & Admin** → **IAM**
2. Find your service account
3. Grant roles:
   - `Storage Object Creator` (for GCS)
   - `BigQuery Data Editor` (for BigQuery)
4. Wait 1-2 minutes for permissions to propagate
5. Re-run `setup.sh`

## Environment Files Created

### `.env`
- **Location:** Project root
- **Contains:** GCP project settings, dataset names, pipeline configuration
- **Safety:** Added to `.gitignore`

### `~/.dbt/profiles.yml`
- **Location:** User home directory (`.dbt/` folder)
- **Contains:** dbt BigQuery connection (service account keyfile path)
- **Safety:** Permissions restricted to user only

### `.gcp-credentials.json`
- **Location:** Project root
- **Contains:** GCP service account credentials
- **Safety:** Added to `.gitignore`, file permissions 0600

## Validation

After setup completes, verify everything works:

```bash
# Check environment status
uv run embrapa doctor

# Run dbt tests
make dbt-test

# Build dbt dev models
make dbt-build
```

## Next Steps

1. Review `.env` and adjust settings if needed
2. Ensure GCP service account has proper IAM roles
3. Run `uv run embrapa ingest ibge` to test ingestion
4. Happy coding! 🚀

## Advanced: Manual Setup (if scripts don't work)

If the bootstrap scripts encounter issues, you can set up manually:

1. **Install Python 3.8+** from https://www.python.org/downloads/
2. **Install uv:**
   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. **Run setup script:**
   ```bash
   python3 setup_dev_env.py --credentials-file /path/to/service-account.json
   ```

## Support

For issues or questions:
- **CLAUDE.md** — Project architecture and commands
- **GitHub Issues** — https://github.com/igorrflorentino/embrapa-dashboard-commodities/issues
- **Contributing** — See CLAUDE.md for setup and development workflow

## Architecture Diagram

```
Fresh Machine
    ↓
setup.sh / setup.bat
    ↓
[Detect Python]
    ├─→ Found? Continue
    └─→ Not found? Auto-install
    ↓
[Detect uv]
    ├─→ Found? Continue
    └─→ Not found? Auto-install
    ↓
setup_dev_env.py
    ├─→ Get GCP Credentials
    ├─→ Create .env
    ├─→ Create dbt/profiles.yml
    ├─→ Update .gitignore
    └─→ Run embrapa doctor
    ↓
✅ Ready to develop!
```
