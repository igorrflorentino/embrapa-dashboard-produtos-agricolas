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
python3 test_setup.py
```

## What Gets Tested

The test suite validates **28 critical components** across 9 categories:

### 1️⃣ File Existence (8 tests)
- ✅ `.env` file exists
- ✅ `.gcp-credentials.json` exists
- ✅ `~/.dbt/profiles.yml` exists
- ✅ All bootstrap scripts present
- ✅ Documentation files present

### 2️⃣ Environment Configuration (6 tests)
- ✅ `.env` file is readable
- ✅ Required config keys present:
  - `GCP_PROJECT_ID`
  - `GCS_BUCKET`
  - `BQ_LOCATION`
  - `BQ_BRONZE_IBGE_DATASET`
  - `BCB_INFLATION_SERIES`
  - `IBGE_PRODUCT_CODES`

### 3️⃣ GCP Credentials (4 tests)
- ✅ Credentials file is valid JSON
- ✅ Required fields present:
  - `project_id`
  - `private_key`
  - `client_email`
  - `type`

### 4️⃣ dbt Configuration (5 tests)
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

Total: 28 tests
Passed: 28 ✅
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
  run: python3 test_setup.py
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

- **SETUP.md** — Environment setup documentation
- **CLAUDE.md** — Project architecture and commands
- **setup_dev_env.py** — Setup script (see for test implementation)
- **test_setup.py** — Test script source code

## Support

For test failures or questions:
1. Check TESTING.md troubleshooting section
2. Review SETUP.md for setup issues
3. Check CLAUDE.md for architecture details
4. Open GitHub issue if problem persists
