.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        ingest-ibge-historical \
        dbt-deps dbt-build dbt-build-prod dbt-build-prod-with-backup backup-gold \
        dbt-test dbt-clean lint test clean \
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

dbt-test:
	cd $(DBT_DIR) && $(PY) dbt test

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
