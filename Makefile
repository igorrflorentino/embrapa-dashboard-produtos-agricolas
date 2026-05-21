.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        dbt-deps dbt-build dbt-build-prod dbt-test dbt-clean lint test clean \
        precommit-install precommit-run \
        dashboard-sync dashboard-run dashboard-build dashboard-deploy

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

precommit-install:    ## Install git hooks defined in .pre-commit-config.yaml
	$(PY) pre-commit install

precommit-run:        ## Run all hooks against every file (not just staged)
	$(PY) pre-commit run --all-files

clean:
	rm -rf .pytest_cache .ruff_cache $(DBT_DIR)/target $(DBT_DIR)/dbt_packages $(DBT_DIR)/logs

# ─── Dash dashboard (Cloud Run target) ─────────────────────────────────────
DASH_IMAGE  ?= embrapa-dashboard:local
DASH_SERVICE ?= embrapa-commodities-dashboard
DASH_REGION ?= us-central1

dashboard-sync:    ## Install dashboard runtime deps
	uv sync --extra dashboard

dashboard-run: dashboard-sync    ## Local dev server on http://localhost:8080
	$(PY) --extra dashboard python -m embrapa_commodities.dashboard.app

dashboard-build:    ## Build the Cloud Run image locally
	docker build -f deploy/Dockerfile -t $(DASH_IMAGE) .

dashboard-deploy:    ## Deploy the dashboard to Cloud Run (uses gcloud's active project)
	gcloud run deploy $(DASH_SERVICE) \
	  --source . \
	  --region $(DASH_REGION) \
	  --allow-unauthenticated \
	  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 5 \
	  --port 8080 \
	  --set-env-vars GCP_PROJECT_ID=$$GCP_PROJECT_ID,BQ_GOLD_DATASET=gold,BQ_LOCATION=$${BQ_LOCATION:-US}
