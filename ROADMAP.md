# Roadmap — Embrapa Commodities Dashboard

> The project's future vision. Goals organized by time horizon.
> This document is updated as the project evolves.

---

## 🟢 Short Term (1–3 months)

Focus: **stabilization, observability and basic automation**.

### Pipeline & Data
- [x] **Ingestion orchestration**: `embrapa ingest all` packaged as a **Cloud Run Job** (batch, not Service) + a **Cloud Scheduler** trigger overnight (off-peak) — artifacts in [`deploy/ingestion/`](deploy/ingestion/) (`make ingest-job-deploy` / `make ingest-job-schedule`); re-run `make ingest-job-deploy` after schema/arg changes. Leverages the resilience from `tenacity` (retry/slow-byte) + the BCB/COMEX delta. See [ARCHITECTURE § Ingestion orchestration](ARCHITECTURE.md#ingestion-orchestration-cloud-run-job--cloud-scheduler).
- [ ] Ingestion failure notifications (email or Slack webhook)
- [x] Integrate SQLFluff into CI (dedicated gating `sqlfluff` CI job)
- [ ] End-to-end integrity tests (row counts Bronze → Silver → Gold)

### Visualization (two parallel paths)

> Gold is consumed by **Looker Studio** (no-code, direct on Gold) **and** by a
> **React SPA + Flask webapi (live)** on Cloud Run. The items below apply to the
> dedicated dashboard; Looker covers the no-code path in parallel. See
> [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumption.

- [x] **Pushdown Computing** — **stateless** dashboard: UI filters → SQL `@param` on the `serving` layer, with `flask-caching` (TTL) on the results. Replaces the in-memory/Pandas design (OOM/concurrency risk). Backend (BFF) already in [`src/embrapa_commodities/serving/`](src/embrapa_commodities/serving/).
- [x] **Dynamic curation (SCD Type 2)** — append-only log `code_industrialization_log` + view `dim_code_industrialization_scd2` (`lead()`); live current-classification read in the UI; author via IAP header. Without overwriting Gold.
- [x] Curation UI components + CSV/Excel export (`ViewCuration.jsx` + `csvExport.js`)
- [ ] UX improvements based on researcher feedback

### Quality
- [ ] Increase test coverage to ≥ 80%
- [ ] Contract tests for external APIs (IBGE SIDRA, BCB SGS)
- [x] Operations / troubleshooting runbook — [`docs/operations_runbook.md`](docs/operations_runbook.md)

### Documentation
- [ ] Document the CLI API (auto-generated via `embrapa --help`)
- [x] ER diagram of the Gold data model — [`docs/gold_data_model.md`](docs/gold_data_model.md) (ER diagram + join guide)
- [ ] Onboarding guide for new contributors

---

## 🟡 Medium Term (3–6 months)

Focus: **new data sources, IaC and dashboard improvements**.

### New Data Sources
- [ ] CONAB — production prices and costs
- [ ] CEPEA — agricultural price indicators
- [ ] FAO — international production data for benchmarking
- [ ] Expand IBGE product coverage (beyond extractive vegetable production)

### Infrastructure
- [ ] Terraform / Pulumi for provisioning the GCP project (IaC)
- [~] Workload Identity Federation for CI/CD (eliminate secrets) — already partially in place (`release.yml` + `dbt-build-prod.yml` + the `sqlfluff` job authenticate via WIF/OIDC, no long-lived keys); remaining: extend to any CI paths still using keys
- [ ] Separate staging environment (between local dev and prod)
- [~] Automated deploy pipeline (CI/CD → Cloud Run) — build/publish DONE (`release.yml` publishes a versioned image to Artifact Registry; v1.0.0 released + deployed); remaining: auto-deploy the released tag to Cloud Run

### Dashboard
- [x] Product comparison page (`ViewProductCompare.jsx`)
- [x] Interactive geographic maps — state-level (UF) choropleth (`BrazilChoropleth.jsx`)
  - [x] Municipality-level + sub-UF geography (meso/micro + intermediária/imediata + live município) — delivered v1.5.2 (`dim_geo_municipio`, `/api/municipio-yearly`, `/api/geo-mesh`)
- [ ] Configurable light/dark theme
- [ ] Internationalization (i18n) — English support

### Data
- [ ] Optimized partitioning of the Gold tables (clustering by product_code + state_acronym)
- [x] **`serving/` layer (Pushdown Computing)** — marts pre-aggregated at the exact chart grains + conformed dimensions (`dim_date`, `dim_geo_br`), reducing the scan from **GB → MB** for the dashboard. Replaces the previous "deliberately never pre-aggregate" stance; Gold remains the comprehensive per-source table and `serving` derives from it (see [`ARCHITECTURE.md`](ARCHITECTURE.md#serving-layer--pushdown-computing-webapi-dashboard) § Serving Layer)
- [ ] Incremental materializations in the serving marts **if** the volume grows (today `table` full-refresh in the overnight rebuild)
- [x] Data freshness monitoring (dbt source freshness) — `dbt-source-freshness.yml` runs daily

---

## 🔴 Long Term (6–12 months)

Focus: **scale, intelligence and openness**.

### Intelligence & Analysis
- [ ] Predictive production models (time series, seasonality)
- [ ] Automatic anomaly alerts in the data (unexpected drop/spike)
- [ ] Integration with Vertex AI for advanced analyses
- [ ] Natural Language Query — natural-language questions over the data

### Scale
- [ ] Support for multiple GCP projects (multi-tenant)
- [ ] Public REST API for programmatic querying of the Gold data
- [ ] Data sharing via BigQuery Analytics Hub
- [ ] Orchestration with Apache Airflow / Cloud Composer

### Community & Openness
- [ ] Publication of a public dataset (BigQuery public dataset or dados.gov.br)
- [ ] Technical documentation in English (documentation internationalization)
- [ ] Contributions to the open-source packages used
- [ ] Presentations at conferences (PyCon, dbt Coalesce, Google Cloud Next)

### Governance
- [ ] Data catalog (Google Data Catalog or DataHub)
- [ ] Visual data lineage (integration with dbt docs)
- [ ] Formal SLA for data updates
- [ ] Data retention policy (lifecycle rules in GCS)

---

## 📌 Guiding Principles

1. **Zero hardcoding** — everything configurable via `.env`
2. **Reproducibility** — anyone should be able to recreate the pipeline from scratch
3. **Security first** — no keyfiles, impersonation everywhere
4. **Trustworthy data** — tests, quality flags, an auditable chain index
5. **Operational simplicity** — one `make` or `embrapa` command for each task

---

> 💡 Feature suggestions? Open an [issue](https://github.com/igorrflorentino/embrapa-dashboard-commodities/issues) or see [CONTRIBUTING.md](CONTRIBUTING.md).
