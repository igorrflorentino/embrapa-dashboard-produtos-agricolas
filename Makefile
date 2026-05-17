.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        dbt-deps dbt-build dbt-build-prod dbt-test dbt-clean lint test clean

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

dbt-test:
	cd $(DBT_DIR) && $(PY) dbt test

dbt-clean:
	cd $(DBT_DIR) && $(PY) dbt clean

lint:
	$(PY) ruff check .
	$(PY) ruff format --check .

test:
	$(PY) pytest

clean:
	rm -rf .pytest_cache .ruff_cache $(DBT_DIR)/target $(DBT_DIR)/dbt_packages $(DBT_DIR)/logs
