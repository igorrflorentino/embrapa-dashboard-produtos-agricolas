.PHONY: setup sync auth ingest-all ingest-ibge ingest-bcb-inflation ingest-bcb-currency \
        dbt-deps dbt-build dbt-build-prod dbt-test dbt-clean lint test test-smoke clean \
        precommit-install precommit-run \
        dashboard-sync dashboard-run dashboard-build dashboard-deploy \
        dashboard-smoke dashboard-visual

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

test:    ## Fast unit tests (excludes `-m smoke`; no live BQ required)
	$(PY) pytest -m "not smoke"

test-smoke: dashboard-sync    ## Live-BQ dashboard smoke (HARD-fails without GCP_PROJECT_ID)
	$(PY) --extra dashboard pytest -m smoke

precommit-install:    ## Install git hooks defined in .pre-commit-config.yaml
	$(PY) pre-commit install

precommit-run:        ## Run all hooks against every file (not just staged)
	$(PY) pre-commit run --all-files

clean:
	rm -rf .pytest_cache .ruff_cache $(DBT_DIR)/target $(DBT_DIR)/dbt_packages $(DBT_DIR)/logs

# ─── Dash dashboard (Cloud Run target) ─────────────────────────────────────
DASH_IMAGE  ?= embrapa-dashboard:local
DASH_SERVICE ?= embrapa-dashboard-commodities
DASH_REGION ?= us-central1

dashboard-sync:    ## Install dashboard runtime deps
	uv sync --extra dashboard

dashboard-run: dashboard-sync    ## Local dev server on http://localhost:8080
	$(PY) --extra dashboard python -m embrapa_commodities.dashboard.app

dashboard-smoke: dashboard-sync    ## Boot + HTTP/callback smoke (live BQ render)
	$(PY) --extra dashboard python scripts/dashboard_smoke.py

dashboard-visual: ## Headless-browser visual check (screenshots → artifacts/)
	uv sync --extra dashboard --extra visual
	$(PY) --extra dashboard --extra visual python -m playwright install chromium
	$(PY) --extra dashboard --extra visual python scripts/dashboard_visual_check.py

dashboard-build:    ## Build the Cloud Run image locally
	docker build -t $(DASH_IMAGE) .

dashboard-deploy:    ## Deploy the dashboard to Cloud Run (uses gcloud's active project)
	# Auth posture: --no-allow-unauthenticated + --invoker-iam-check. The
	# dashboard is gated by roles/run.invoker — grant it per-user via
	# docs/auth.md. Do NOT flip either flag without re-auditing what Gold
	# exposes. NOTE: BOTH flags are required. --no-allow-unauthenticated
	# removes the allUsers IAM binding, but Cloud Run also stores an
	# `invoker-iam-disabled` annotation independently that bypasses ALL IAM
	# checks; --invoker-iam-check is what clears that annotation.
	gcloud run deploy $(DASH_SERVICE) \
	  --source . \
	  --region $(DASH_REGION) \
	  --no-allow-unauthenticated \
	  --invoker-iam-check \
	  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 5 \
	  --port 8080 \
	  --cpu-boost \
	  --set-env-vars GCP_PROJECT_ID=$$GCP_PROJECT_ID,BQ_GOLD_DATASET=gold,BQ_LOCATION=$${BQ_LOCATION:-us-central1},CLOUD_RUN_REGION=$(DASH_REGION)
