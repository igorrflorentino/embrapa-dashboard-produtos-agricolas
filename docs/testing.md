# Testing Guide

Comprehensive testing for the development environment setup.

## Quick Test

Run all environment validation tests in one command:

### macOS / Linux
```bash
./test.sh
```

### Windows
```cmd
test.bat
```

### Or directly with Python
```bash
python3 scripts/test_setup.py
```

## What Gets Tested

The test suite validates critical components across 9 categories. The exact
count varies by auth mode (~27 in enterprise / impersonation mode, ~31 in
legacy keyfile mode):

### 1️⃣ File Existence (8 checks)
- ✅ `.env` file exists
- ✅ `~/.dbt/profiles.yml` exists
- ✅ Bootstrap scripts present: `setup.sh`, `setup.bat`, `setup.ps1`, `scripts/setup_dev_env.py`
- ✅ `docs/setup.md` present
- ✅ `.gcp-credentials.json` — required in legacy mode, optional in enterprise mode

### 2️⃣ Environment Configuration (7 checks)
- ✅ `.env` file is readable
- ✅ Required config keys present:
  - `GCP_PROJECT_ID`
  - `GCS_BUCKET`
  - `BQ_LOCATION`
  - `BQ_BRONZE_IBGE_DATASET`
  - `BCB_INFLATION_SERIES`
  - `IBGE_PRODUCT_CODES`

### 3️⃣ GCP Credentials (1–5 checks)
- **Legacy:** Credentials file is valid JSON + required fields (`project_id`, `private_key`, `client_email`, `type`)
- **Enterprise:** Application Default Credentials (ADC) reachable via `gcloud auth application-default print-access-token`

### 4️⃣ dbt Configuration (6 checks)
- ✅ `profiles.yml` is readable
- ✅ Required sections present:
  - `embrapa_commodities:`
  - `dev:` and `prod:` targets
  - `type: bigquery`
  - `method: service-account` (legacy) **or** `method: oauth` (enterprise)

### 5️⃣ Python & Dependencies (1 test)
- ✅ Python >= 3.8 available

### 6️⃣ Build Tools (1 test)
- ✅ `uv` command available and working

### 7️⃣ dbt (1 test)
- ✅ `dbt` accessible via `uv run`

### 8️⃣ Embrapa Pipeline (1 test)
- ✅ `embrapa doctor` passes all checks:
  - `.env` parsed ✓
  - GCP credentials accessible ✓
  - BigQuery reachable ✓
  - GCS bucket accessible ✓
  - IBGE SIDRA API reachable ✓
  - BCB SGS API reachable ✓
  - Bronze tables present ✓

### 9️⃣ BigQuery Connection (1 test)
- ✅ `dbt debug` succeeds:
  - Service account authentication ✓
  - BigQuery connection OK ✓
  - Schema and dataset accessible ✓

## Test Output Example

```
============================================================
  1️⃣  File Existence Tests
============================================================

  ➜ File exists: .env... ✅
  ➜ File exists: .gcp-credentials.json... ✅
  ...

============================================================
  📊 Test Summary
============================================================

Total: 27 tests
Passed: 27 ✅
Failed: 0 ❌

🎉 All tests passed! Environment is ready.
```

## Exit Codes

- **0** — All tests passed ✅
- **1** — One or more tests failed ❌

## Troubleshooting

### Test Fails: "File exists: .env"
Run setup again:
```bash
./setup.sh
```

### Test Fails: "Config key present: GCP_PROJECT_ID"
Edit `.env` and ensure all required keys are present. See CLAUDE.md for defaults.

### Test Fails: "GCP Credentials"
The credentials file is invalid JSON. Verify:
1. File is valid JSON (use https://jsonlint.com/)
2. All required fields are present
3. No special characters in file path

### Test Fails: "dbt debug (BigQuery connection)"
This usually means:
1. Service account doesn't have BigQuery permissions
2. Credentials file path is wrong in `profiles.yml`
3. Network connectivity issue

Check permissions in Google Cloud Console:
- IAM & Admin → IAM
- Find service account
- Verify roles: `BigQuery Data Editor` and `Storage Object Creator`

### Test Fails: "embrapa doctor"
Run manually to see detailed output:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/.gcp-credentials.json
uv run embrapa doctor
```

## Dashboard testing

The dashboard (`src/embrapa_commodities/dashboard/`) has its own test layer
that intentionally sits *outside* the default `make test` loop. The split
was driven by the 2026-05 audit (P1, action item #4): contributors used to
get a green `make test` without any dashboard verification at all.

### Three layers, three audiences

| Layer | Command | When it runs | Needs live BQ? | Where it lives |
|-------|---------|--------------|----------------|----------------|
| **1. Unit tests** | `make test` | Every dev, every commit | No | `tests/` (excludes `-m smoke`) |
| **2. Dashboard smoke** | `make test-smoke` | Devs touching the dashboard, before PR | **Yes** — hard-fails without `GCP_PROJECT_ID` | `tests/test_dashboard_smoke.py` (marked `@pytest.mark.smoke`) |
| **3. CI gate** | GitHub Actions runs `make test-smoke` on every PR | Always, automatically | Yes (Workload Identity Federation) | `.github/workflows/dashboard-smoke.yml` |

### Why the smoke is opt-in, not always-on

The smoke boots the Dash server, hits `/_health` and `/`, lists Dash
callbacks, and forces a live BigQuery route render. **It requires real
credentials** (`GCP_PROJECT_ID` + Application Default Credentials).

- `make test` runs `pytest -m "not smoke"` so it stays fast and credential-free.
  Forks, fresh clones, and offline work all get a clean green.
- `make test-smoke` runs `pytest -m smoke` and **hard-fails** (not skips!) if
  `GCP_PROJECT_ID` is unset. This is deliberate: a silent skip on missing
  creds is the *exact anti-pattern the audit flagged*. Whoever invoked the
  smoke owes the environment — a green `test-smoke` must mean "live BQ
  rendered the dashboard", never "I didn't have creds, so nothing ran".

### When to run what

| Scenario | Command |
|----------|---------|
| Routine work, no dashboard changes | `make test` |
| About to PR a change under `src/embrapa_commodities/dashboard/**` | `make test` **then** `make test-smoke` |
| About to PR a Gold model change (could break the dashboard's data contract) | `make test-smoke` |
| UI/visual change you want to attach to the PR description | `make dashboard-visual` (Chromium screenshots → `artifacts/`) |
| Gate a Cloud Run deploy against a live URL | `uv run python scripts/dashboard_smoke.py --no-launch --url https://...` |

`make dashboard-visual` is intentionally **not** in pytest — headless-Chromium
installs and rendering flakiness would degrade CI reliability without adding
much signal beyond what the smoke already proves. Keep it as a manual step
when a PR's diff includes UI changes worth eyeballing.

### CI is the source of truth

The local smoke is for fast feedback during a change. The merge gate is
`.github/workflows/dashboard-smoke.yml`, which:

- Runs on PRs that touch the dashboard, `scripts/dashboard_smoke.py`, the
  Gold dbt models, or `pyproject.toml`/`uv.lock`.
- Authenticates to GCP via **Workload Identity Federation** — no private
  keys live in the repo; GitHub mints a short-lived OIDC token at job time
  and exchanges it for a SA token via the WIF provider.
- Skips on fork PRs (they can't reach the WIF provider; this is the intended
  security boundary).
- Uploads `artifacts/dashboard_smoke_server.log` on failure so you can read
  the server crash without reproducing locally.

The one-time GCP setup (WIF pool, provider, SA binding) is documented as a
header comment at the top of the workflow file.

## Manual Testing

Beyond automated tests, you can verify functionality manually:

### Test dbt
```bash
# Validate dbt configuration
make dbt-test

# Build dev models
make dbt-build

# Or run specific dbt command
uv run dbt run --select silver_ibge_pevs
```

### Test ingestion
```bash
# Simulate ingestion (dry-run)
uv run embrapa ingest ibge --help

# Test IBGE discovery
uv run embrapa discover ibge-periods --table-id 289

# Test BCB discovery
uv run embrapa discover bcb-series 433
```

### Test database connectivity
```bash
# Test BigQuery directly
uv run dbt run-operation validate_connection
```

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```bash
#!/bin/bash
# GitHub Actions example
- name: Test environment setup
  run: python3 scripts/test_setup.py
```

## Test Coverage

| Component | Type | Status |
|-----------|------|--------|
| File structure | Static | ✅ Automated |
| Configuration | Static | ✅ Automated |
| Credentials | Static + Dynamic | ✅ Automated |
| Python/uv | Environment | ✅ Automated |
| dbt | Tool | ✅ Automated |
| BigQuery | Network | ✅ Automated |
| GCS | Network | ✅ Automated (via embrapa doctor) |
| Ingestion | Integration | ⚠️ Manual only |
| dbt models | Integration | ⚠️ Manual only |

## Next Steps After Testing

If all tests pass, you're ready to:

1. **Run the pipeline:** `make dbt-build`
2. **Test ingestion:** `uv run embrapa ingest ibge`
3. **Monitor pipeline:** `uv run embrapa monitor`
4. **Start development:** Create your feature branch

## Additional Resources

- **setup.md** — Environment setup documentation
- **CLAUDE.md** — Project architecture and commands
- **scripts/setup_dev_env.py** — Setup script (see for test implementation)
- **scripts/test_setup.py** — Test script source code

## Support

For test failures or questions:
1. Check testing.md troubleshooting section
2. Review setup.md for setup issues
3. Check CLAUDE.md for architecture details
4. Open GitHub issue if problem persists
