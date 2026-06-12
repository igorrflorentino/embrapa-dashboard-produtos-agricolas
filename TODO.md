# TODO — Embrapa Commodities Dashboard

> The project's macro list of pending and completed tasks.
> Updated manually as development progresses.

---

## ✅ Completed

### Backend (data pipeline)
- [x] Complete Medallion pipeline (Bronze → Silver → Gold)
- [x] IBGE PEVS ingestion via the SIDRA API
- [x] BCB ingestion (IPCA/IGP-M/IGP-DI inflation + USD/EUR FX)
- [x] Delta ingestion for the BCB pipelines (new data only)
- [x] Chunked IBGE ingestion (`ibge-batch --chunk-years`)
- [x] IPCA chain index (Silver) for historical deflation
- [x] Seed `historical_currency_factors` for currency reforms
- [x] dev/prod separation in the dbt schemas (`dbt_dev_*` vs `silver`/`gold`)
- [x] Auto-expiration of dev tables (7 days via `apply_dev_ttl`)
- [x] Unified CLI with Typer (`embrapa ingest|discover|dbt|doctor|backup-gold|monitor`)
- [x] Service Account Impersonation (OAuth, no keyfiles)
- [x] Pre-commit hooks (gitleaks + ruff + file-hygiene)
- [x] CI/CD GitHub Actions (lint + test + dbt parse)
- [x] Gold backup → GCS (`embrapa backup-gold`, introspective by prefix)
- [x] `embrapa doctor` for health diagnostics
- [x] JSONL observability + `embrapa monitor` (IBGE and BCB)
- [x] Cross-platform automated setup (`setup.sh`, `setup.bat`, `setup.ps1`)
- [x] Setup, IAM, cost safety, ownership transfer documentation
- [x] `gold_<source>_<form>` Gold convention + one comprehensive table per source
- [x] Groundwork ready for multi-source (registries `cli.INGESTS` / `doctor.*`, `core/`, the `adding_a_data_source.md` guide)

### Visualization layer

> The Dash + Plotly UI and the Cloud Run deploy **were delivered in v0.1.0 and
> removed on 2026-05-29** for reconstruction in the Claude Design System (see [`CHANGELOG.md`](CHANGELOG.md)).
> They are neither "pending" nor "completed" — they are a consumption path **under
> reconstruction**. The backend already feeds the **two parallel consumption
> paths** (Looker Studio + the Dash/Cloud Run dashboard); see [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumption.

- [x] Consumption via **Looker Studio** (direct connection to Gold) — available
- [ ] **Dedicated dashboard (HTML/CSS + Dash) on Cloud Run** — under reconstruction (Claude Design System); reintroduces Dockerfile + Cloud Run deploy + read-only SA

---

## 🔲 Pending

Pending tasks are prioritized by time horizon in [`ROADMAP.md`](ROADMAP.md).

For the historical record of features delivered per version, see [`CHANGELOG.md`](CHANGELOG.md).

---

> 💡 For details on complex features, see the [`PLANS/`](PLANS/) directory.

