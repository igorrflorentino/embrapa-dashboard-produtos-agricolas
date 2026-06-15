.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        ingest-ibge-historical reconcile ingest-job-deploy ingest-job-schedule \
        ingest-job-reconcile-schedule ingest-job-comtrade-schedule ingest-job-pam-schedule \
        ingest-job-alert iam-grant \
        webapi-run webapi-deploy \
        dbt-deps dbt-build dbt-build-prod dbt-build-prod-with-backup backup-gold \
        dbt-build-curation serving-sync ensure-curation \
        dbt-test dbt-source-freshness dbt-clean lint sqlfluff test clean \
        precommit-install precommit-run

PY := uv run
DBT_DIR := dbt
# Every dbt invocation goes through this wrapper so the repo-root .env is exported
# first — dbt_project.yml reads its datasets + BCB series codes via env_var(), which
# only sees the process environment. A bare `dbt build` would silently use the
# baked-in env_var() defaults and ignore .env (see scripts/dbt-with-env.sh).
DBT := bash scripts/dbt-with-env.sh

setup:        ## Pin Python and create the virtualenv
	pyenv local 3.12.11
	uv sync

sync:         ## Re-sync dependencies from pyproject.toml + uv.lock
	uv sync

auth:         ## Refresh Application Default Credentials for local dev
	gcloud auth application-default login

ingest-ibge:
	$(PY) embrapa ingest ibge

ingest-bcb-inflation:
	$(PY) embrapa ingest bcb-inflation

ingest-bcb-currency:
	$(PY) embrapa ingest bcb-currency

ingest-all:
	$(PY) embrapa ingest all

ingest-ibge-historical:    ## Ingest IBGE in safe 5-year chunks (for large historical windows)
	$(PY) embrapa ingest ibge-batch --chunk-years 5

reconcile: dbt-deps    ## Deep-refresh: full re-ingest (catches OLD-year revisions) then PROD dbt build
	@echo "[reconcile] Full re-ingest (chunked IBGE + full BCB/COMEX) via LOCAL .env, then a PROD dbt build."
	@echo "[reconcile] WARNING: this uses your LOCAL .env. Verify it matches prod (esp. BCB_CURRENCY_SERIES)"
	@echo "[reconcile]          before running — a drifted local .env will regress Bronze. The deployed Job"
	@echo "[reconcile]          path (make ingest-job-reconcile-schedule) uses the correct prod config and is unaffected."
	$(PY) embrapa ingest reconcile
	$(DBT) build --target prod
	@echo "[reconcile] Done. This may have rewritten HISTORICAL Gold — consider 'make backup-gold'."

ingest-job-deploy:    ## Build + deploy the `embrapa ingest all` Cloud Run Job (reads .env)
	bash deploy/ingestion/deploy.sh

ingest-job-schedule:    ## Create/update the nightly Cloud Scheduler trigger for the job
	bash deploy/ingestion/schedule.sh

ingest-job-reconcile-schedule:    ## Create/update the MONTHLY deep-refresh trigger (Job with --args=reconcile)
	bash deploy/ingestion/schedule_reconcile.sh

ingest-job-comtrade-schedule:    ## Create/update the MONTHLY UN Comtrade backfill trigger (Job with --args=comtrade; needs COMTRADE_API_KEY secret)
	bash deploy/ingestion/schedule_comtrade.sh

ingest-job-pam-schedule:    ## Create/update the MONTHLY IBGE PAM trigger (Job with --args=ibge-pam; needs PAM_* in the deploy allowlist → redeploy)
	bash deploy/ingestion/schedule_pam.sh

ingest-job-alert:    ## Create the Cloud Monitoring alert for ingestion-job failures (needs INGEST_ALERT_EMAIL)
	bash deploy/ingestion/alert.sh

iam-grant:    ## Apply dataset-scoped least-privilege IAM grants (DRY_RUN=1 to preview)
	bash deploy/iam/grant_least_privilege.sh

webapi-run:    ## Run the REST API locally on :8000 (needs .env + ADC; serve the SPA via `cd frontend && npm run dev`)
	uv run --extra webapi python -c "from embrapa_commodities.webapi.app import app; app.run(host='127.0.0.1', port=8000, threaded=True)"

webapi-deploy:    ## Build + deploy the React SPA + Flask REST Cloud Run Service (reads .env)
	bash deploy/webapi/deploy.sh

dbt-deps:
	$(DBT) deps

dbt-build: dbt-deps    ## Dev: silver+gold in dbt_dev_silver / dbt_dev_gold
	$(DBT) build

dbt-build-prod: dbt-deps    ## Prod: silver+gold in silver / gold (real datasets)
	$(DBT) build --target prod

backup-gold:    ## Snapshot prod Gold tables to gs://${GCS_BUCKET}/backups/run=<ts>/
	$(PY) embrapa backup-gold

dbt-build-prod-with-backup: dbt-build-prod backup-gold    ## Recommended prod path: build then snapshot
	@echo "[ok] prod build + Gold snapshot complete"

serving-sync:    ## Install the dashboard data-access extra (flask + flask-caching)
	uv sync --extra serving

ensure-curation:    ## Create the append-only curation log tables (research_inputs.*)
	$(PY) python -c "from embrapa_commodities.serving.curation import ensure_code_industrialization_log_table as c, ensure_flow_market_log_table as f, ensure_curators_table as a; print('code log ready:', c()); print('flow-market log ready:', f()); print('curators table ready:', a())"

dbt-build-curation: dbt-deps    ## Dev build INCLUDING the gated SCD2 curation dim (needs the log table)
	$(DBT) build --vars 'enable_curation: true'

dbt-test:
	$(DBT) test

dbt-source-freshness: dbt-deps    ## Check Bronze source staleness vs the freshness thresholds (needs a profile + warehouse)
	$(DBT) source freshness

sqlfluff:    ## Lint dbt SQL models with SQLFluff (BigQuery dialect; needs a dbt profile)
	cd $(DBT_DIR) && $(PY) sqlfluff lint models

dbt-clean:
	cd $(DBT_DIR) && $(PY) dbt clean

lint:
	$(PY) ruff check .
	$(PY) ruff format --check .

test:    ## Run the unit test suite (credential-free, no live BQ required)
	$(PY) pytest

precommit-install:    ## Install git hooks defined in .pre-commit-config.yaml
	$(PY) pre-commit install

precommit-run:        ## Run all hooks against every file (not just staged)
	$(PY) pre-commit run --all-files

clean:
	rm -rf .pytest_cache .ruff_cache $(DBT_DIR)/target $(DBT_DIR)/dbt_packages $(DBT_DIR)/logs
