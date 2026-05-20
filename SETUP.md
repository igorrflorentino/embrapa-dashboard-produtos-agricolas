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
4. ✅ Loads GCP credentials (with fallback strategy)
5. ✅ Creates `.env` file with configuration
6. ✅ Creates `~/.dbt/profiles.yml` for BigQuery
7. ✅ Protects credentials in `.gitignore`
8. ✅ Validates entire setup with `embrapa doctor`

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
- Cross-platform setup logic
- Gets GCP credentials (with 3-level fallback)
- Creates `.env` and dbt profiles
- Runs validation checks

## GCP Credentials Strategy

The setup script tries to find your credentials in this order:

### 1️⃣ Environment Variable (GOOGLE_APPLICATION_CREDENTIALS)
If you already have this variable set:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
./setup.sh
```

### 2️⃣ File Argument
Pass credentials file as argument:
```bash
./setup.sh --credentials-file /path/to/service-account.json
```

### 3️⃣ Interactive Prompt
If neither above works, the script will ask you to paste your service account JSON.

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
