# Roadmap — Embrapa Commodities Dashboard

> The project's future vision. Goals organized by time horizon.
> This document is updated as the project evolves.

---

## 🟢 Short Term (1–3 months)

Focus: **stabilization, observability and basic automation**.

### Pipeline & Data
- [~] **Ingestion orchestration**: `embrapa ingest all` packaged as a **Cloud Run Job** (batch, not Service) + a **Cloud Scheduler** trigger overnight (off-peak) — artifacts in [`deploy/ingestion/`](deploy/ingestion/) (`make ingest-job-deploy` / `make ingest-job-schedule`); the operator still needs to run the deploy on GCP. Leverages the resilience from `tenacity` (retry/slow-byte) + the BCB/COMEX delta. See [ARCHITECTURE § Ingestion orchestration](ARCHITECTURE.md#ingestion-orchestration-cloud-run-job--cloud-scheduler).
- [ ] Ingestion failure notifications (email or Slack webhook)
- [ ] Integrate SQLFluff into CI (currently run manually)
- [ ] End-to-end integrity tests (row counts Bronze → Silver → Gold)

### Visualization (two parallel paths)

> Gold is consumed by **Looker Studio** (no-code, direct on Gold) **and** by a
> **dedicated Dash + HTML/CSS dashboard on Cloud Run** (under reconstruction in the
> Claude Design System). The items below apply to the dedicated dashboard; Looker
> covers the no-code path in parallel. See [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumption.

- [x] **Pushdown Computing** — **stateless** dashboard: UI filters → SQL `@param` on the `serving` layer, with `flask-caching` (TTL) on the results. Replaces the in-memory/Pandas design (OOM/concurrency risk). Backend (BFF) already in [`src/embrapa_commodities/serving/`](src/embrapa_commodities/serving/).
- [x] **Dynamic curation (SCD Type 2)** — append-only log `code_industrialization_log` + view `dim_code_industrialization_scd2` (`lead()`); live current-classification read in the UI; author via IAP header. Without overwriting Gold.
- [ ] Curation UI components + CSV/Excel export (arriving with the Design System handoff)
- [ ] UX improvements based on researcher feedback

### Quality
- [ ] Increase test coverage to ≥ 80%
- [ ] Contract tests for external APIs (IBGE SIDRA, BCB SGS)
- [ ] Operations / troubleshooting runbook

### Documentation
- [ ] Document the CLI API (auto-generated via `embrapa --help`)
- [ ] ER diagram of the Gold data model
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
- [ ] Workload Identity Federation for CI/CD (eliminate secrets)
- [ ] Separate staging environment (between local dev and prod)
- [ ] Automated deploy pipeline (CI/CD → Cloud Run)

### Dashboard
- [ ] Product comparison page
- [ ] Interactive geographic maps (choropleth by state/municipality)
- [ ] Configurable light/dark theme
- [ ] Internationalization (i18n) — English support

### Data
- [ ] Optimized partitioning of the Gold tables (clustering by product_code + state_acronym)
- [x] **`serving/` layer (Pushdown Computing)** — marts pre-aggregated at the exact chart grains + conformed dimensions (`dim_date`, `dim_geo_br`), reducing the scan from **GB → MB** for the dashboard. Replaces the previous "deliberately never pre-aggregate" stance; Gold remains the comprehensive per-source table and `serving` derives from it (see [`ARCHITECTURE.md`](ARCHITECTURE.md#serving-layer--pushdown-computing-dash-dashboard) § Serving Layer)
- [ ] Incremental materializations in the serving marts **if** the volume grows (today `table` full-refresh in the overnight rebuild)
- [ ] Data freshness monitoring (dbt source freshness)

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
