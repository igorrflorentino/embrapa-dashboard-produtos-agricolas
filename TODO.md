# TODO — Embrapa Commodities Dashboard

> The project's macro list of pending and completed tasks.
> Updated manually as development progresses.

---

## ✅ Completed

### Backend (data pipeline)

The foundation is shipped: the full Medallion pipeline (Bronze → Silver → Gold)
with IBGE PEVS + BCB ingestion, the unified `embrapa` CLI, dev/prod schema
separation, CI/CD, backups, observability, and the multi-source groundwork.

For the per-version log of every delivered feature, see [`CHANGELOG.md`](CHANGELOG.md)
— the canonical record. This list is intentionally not a hand-maintained mirror,
so the two stop drifting.

### Visualization layer

> The backend feeds the **two parallel consumption paths** (Looker Studio + the
> custom React/Cloud Run dashboard); see [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumption.

- [x] Consumption via **Looker Studio** (direct connection to Gold) — available
- [x] **Dedicated dashboard (React SPA + Flask REST webapi + Plotly.js) on Cloud Run behind direct IAP** — live

---

## 🔲 Pending

Pending tasks are prioritized by time horizon in [`ROADMAP.md`](ROADMAP.md).

For the historical record of features delivered per version, see [`CHANGELOG.md`](CHANGELOG.md).

---

> 💡 For details on complex features, see the [`PLANS/`](PLANS/) directory.

