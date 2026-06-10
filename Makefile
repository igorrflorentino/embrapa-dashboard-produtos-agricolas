.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        ingest-ibge-historical ingest-job-deploy ingest-job-schedule iam-grant \
        dashboard-run dashboard-deploy \
        dbt-deps dbt-build dbt-build-prod dbt-build-prod-with-backup backup-gold \
        dbt-build-curation serving-sync ensure-curation \
        dbt-test dbt-clean lint sqlfluff test clean \
        precommit-install precommit-run

PY := uv run
DBT_DIR := dbt

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

ingest-job-deploy:    ## Build + deploy the `embrapa ingest all` Cloud Run Job (reads .env)
	bash deploy/ingestion/deploy.sh

ingest-job-schedule:    ## Create/update the nightly Cloud Scheduler trigger for the job
	bash deploy/ingestion/schedule.sh

iam-grant:    ## Apply dataset-scoped least-privilege IAM grants (DRY_RUN=1 to preview)
	bash deploy/iam/grant_least_privilege.sh

webapi-run:    ## Run the REST API locally on :8000 (needs .env + ADC; serve the SPA via `cd frontend && npm run dev`)
	uv run --extra webapi python -c "from embrapa_commodities.webapi.app import app; app.run(host='127.0.0.1', port=8000, threaded=True)"

webapi-deploy:    ## Build + deploy the React SPA + Flask REST Cloud Run Service (reads .env)
	bash deploy/webapi/deploy.sh

dbt-deps:
	cd $(DBT_DIR) && $(PY) dbt deps

dbt-build: dbt-deps    ## Dev: silver+gold in dbt_dev_silver / dbt_dev_gold
	cd $(DBT_DIR) && $(PY) dbt build

dbt-build-prod: dbt-deps    ## Prod: silver+gold in silver / gold (real datasets)
	cd $(DBT_DIR) && $(PY) dbt build --target prod

backup-gold:    ## Snapshot prod Gold tables to gs://${GCS_BUCKET}/backups/run=<ts>/
	$(PY) embrapa backup-gold

dbt-build-prod-with-backup: dbt-build-prod backup-gold    ## Recommended prod path: build then snapshot
	@echo "[ok] prod build + Gold snapshot complete"

serving-sync:    ## Install the dashboard data-access extra (flask + flask-caching)
	uv sync --extra serving

ensure-curation:    ## Create the append-only curation log table (research_inputs.*)
	$(PY) python -c "from embrapa_commodities.serving.curation import ensure_curation_log_table as e; print('curation log ready:', e())"

dbt-build-curation: dbt-deps    ## Dev build INCLUDING the gated SCD2 curation dim (needs the log table)
	cd $(DBT_DIR) && $(PY) dbt build --vars 'enable_curation: true'

dbt-test:
	cd $(DBT_DIR) && $(PY) dbt test

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
