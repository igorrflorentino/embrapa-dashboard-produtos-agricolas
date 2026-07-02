# Embrapa Commodities Dashboard

[![CI](https://github.com/igorrflorentino/embrapa-dashboard-commodities/actions/workflows/ci.yml/badge.svg)](https://github.com/igorrflorentino/embrapa-dashboard-commodities/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3121/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-orange.svg)](LICENSE)
[![uv](https://img.shields.io/badge/pkg-uv-blueviolet)](https://docs.astral.sh/uv/)
[![dbt](https://img.shields.io/badge/transform-dbt-FF694B)](https://www.getdbt.com/)

Medallion pipeline (**Bronze → Silver → Gold**) for **historical and scientific analysis** of Brazilian extractive vegetable production (IBGE PEVS), enriched with FX rates (USD, EUR) and inflation indices (IPCA, IGP-M, IGP-DI) from Brazil's Central Bank. A tool built for **Embrapa researchers** — the focus is on time series and data exploration, **not** business metrics or real-time analytics (data is ingested and transformed in batch).

> 📊 **Two consumption paths, in parallel.** The Gold tables are served by two first-class frontends, both reading the same data:
> 1. **Looker Studio** — direct no-code connection to the Gold table; available today.
> 2. **Dedicated dashboard (React SPA + Flask REST API + Plotly.js) on Google Cloud Run, behind IAP — stateless, Pushdown Computing** — the Flask backend (`src/embrapa_commodities/webapi/`, serving the built SPA and `/api` from one origin) translates each UI filter into **parameterized SQL** (`@param`) over a **`serving`** layer of pre-aggregated marts, with **flask-caching** on the results (without loading Gold into memory); curation via an **append-only log + SCD Type 2**. Live since the 2026-06 Dash→React migration (the previous Dash UI was removed on 2026-05-29 and replaced entirely); the data-access layer lives in `src/embrapa_commodities/serving/`, the frontend in `frontend/`, the deploy in `deploy/webapi/` (`make webapi-deploy`).
>
> The backend (Medallion pipeline + dbt + `embrapa` CLI) is independent of the visualization layer and already feeds both paths. Neither one is exclusive — they can coexist.

```
IBGE PEVS API    ─┐
IBGE PAM API     ─┤
IBGE PPM API     ─┤
BCB Inflation    ─┼─► Python (src/embrapa_commodities) — two-phase
BCB Currency     ─┤   extract → GCS raw/ (verbatim) → filter → BigQuery Bronze
MDIC COMEX CSV   ─┤                                           │
UN Comtrade API  ─┘                                           │
                                                              ▼
                              dbt-bigquery ──► Silver (typed + chained IPCA)
                                                              │
                                                              ▼
        gold_pevs_production · gold_pam_production · gold_ppm_production
              · gold_comex_flows · gold_comtrade_flows (physical tables)
                                                              │
                                       dbt core/ + serving/ ──► conformed dims + marts
                                                              │   pre-aggregated (Pushdown Computing)
                                          ┌───────────────────┴───────────────────┐
                                          ▼                                        ▼
                                   Looker Studio              React SPA + Flask REST @ Cloud Run (IAP)
                                  (direct on Gold)             (stateless · SQL @param + flask-caching)
```

> **Sources today:** IBGE PEVS (`gold_pevs_production`, production), IBGE PAM
> (`gold_pam_production`, annual crop production — área × rendimento), IBGE PPM
> (`gold_ppm_production`, annual livestock — herd + animal production), MDIC COMEX
> (`gold_comex_flows`, Brazilian foreign trade export+import) and UN Comtrade
> (`gold_comtrade_flows`, **global** bilateral trade reporter→partner), all
> enriched with FX/inflation from the BCB. The `gold_<source>_<form>` design is
> extensible — see [docs/adding_a_data_source.md](docs/adding_a_data_source.md).

## Stack

Python 3.12 · `uv` · `dbt-bigquery` · BigQuery · GCS · GitHub Actions · React + Vite + Plotly.js (frontend)

**Consumption (parallel):** Looker Studio (direct on Gold) · React SPA + Flask REST API (`webapi`) @ Cloud Run, behind IAP — *stateless, Pushdown Computing* (SQL `@param` on the `serving` layer + `flask-caching`); live since the 2026-06 Dash→React migration

Full table with technical rationale in [`ARCHITECTURE.md`](ARCHITECTURE.md#technology-stack).

## Everything is configurable via `.env`

Buckets, prefixes, datasets, tables, IBGE product codes and BCB series live in `.env`. See [.env.example](.env.example).

Buckets and datasets are **created automatically** on the first run of `embrapa ingest *`.

## Quickstart

### Automated path (recommended for new machines)

```bash
# macOS / Linux
./setup.sh

# Windows (Command Prompt or PowerShell)
setup.bat
```

The scripts install Python 3.12 and `uv` if missing, detect the best
authentication mode (OAuth impersonation or legacy keyfile) and generate `.env` +
`~/.dbt/profiles.yml`. Details in [docs/setup.md](docs/setup.md).

For sandboxes (including Claude Code Web), `init_dev_env.sh` decodes a
keyfile passed via `GCP_CREDENTIALS_B64` and triggers the same
validation flow. See the *Claude Code Web* section in [docs/setup.md](docs/setup.md).

### Manual path

```bash
# 1. Python + venv
pyenv local 3.12.11
uv sync

# 2. GCP credentials (once per machine)
gcloud auth application-default login

# 3. Configure variables
cp .env.example .env       # adjust GCP_PROJECT_ID and other fields

# 4. (Optional) Discover codes before pinning them in .env
uv run embrapa discover ibge-periods --table-id 289
uv run embrapa discover ibge-products --keywords castanha,madeira,pinheiro
uv run embrapa discover bcb-series 433

# 5. dbt profile (once)
mkdir -p ~/.dbt
cp dbt/profiles.yml.example ~/.dbt/profiles.yml

# 6. Bronze ingestion (Python → GCS → BigQuery)
uv run embrapa ingest all

# 7. Silver + Gold transforms
make dbt-deps
make dbt-build
```

## CLI

```text
embrapa ingest ibge | ibge-pam | ibge-ppm | bcb-inflation | bcb-currency | comex | comtrade | all
embrapa ingest <source> [--from-raw]               # two-phase: extract→raw→bronze; --from-raw re-derives Bronze from raw without re-downloading
embrapa ingest ibge-batch [--chunk-years 5]        # chunked IBGE historical backfill (deadline-safe for large year windows)
embrapa ingest ibge-pam [--full]                   # IBGE PAM (SIDRA table 5457, annual crops); excluded from `ingest all`
embrapa ingest ibge-ppm [--full]                   # IBGE PPM (SIDRA tables 3939+74, annual livestock); excluded from `ingest all`
embrapa ingest comex [--full]                      # COMEX re-downloads only when the ETag changes; --full ignores the check
embrapa ingest comtrade [--full]                   # UN Comtrade (keyed); resumable by daily quota. Outside `ingest all` (key/quota-gated)
embrapa ingest reconcile                            # operator-triggered deep-refresh: full re-ingest of every nightly source (catches OLD-year revisions; a monthly reminder issue nudges)
embrapa discover ibge-periods   [--table-id 289]
embrapa discover ibge-products  --keywords castanha,madeira
embrapa discover bcb-series     <code>            # e.g.: 433
embrapa doctor                                      # environment health check (.env, ADC, BQ/GCS, source APIs, backup freshness)
embrapa backup-gold                                 # snapshot prod Gold tables to gs://${GCS_BUCKET}/backups/run=<ts>/
embrapa monitor [--pipeline <name>]                 # live progress of a running ingest (tails the JSONL event log)
embrapa dbt <args>                                  # e.g.: dbt run --select gold
```

The `discover` commands are **auxiliary and not part of the production pipeline**. Use them to investigate the IBGE/BCB APIs and discover the exact codes you want to set in `.env`.

## Gold monetary conventions

| Column | Meaning | When it is NULL |
|---|---|---|
| `val_yearfx_*` | `val_raw` (already in present-day R$ numéraire, without inflation adjustment) converted by the **average FX of the same year**. Foreign-currency columns are `NULL` pre-1994 so as not to mix old Cruzeiros with present-day values. | Year FX unavailable (e.g. EUR < 1999); or `reference_year < 1994` for USD/EUR. |
| `val_real_ipca_*` | Value projected to today via the **IPCA chain** (absorbs inflation + currency reforms) and converted to current FX. **Use this column for cross-year comparisons.** | Base-year IPCA unavailable. |
| `val_real_igpm_*` | Same, using IGP-M. | Base-year IGP-M unavailable. |
| `val_real_igpdi_*` | Same, using IGP-DI. | Base-year IGP-DI unavailable. |

> The BCB IPCA series (SGS 433) is a monthly variation. The Silver layer chains that percentage into an index number with base 100, making the product `valor_em_cruzeiros * (IPCA_atual / IPCA_ano)` mathematically valid for arriving at present-day Reais — without needing a historical currency conversion table.

## `data_quality_flag`

An 11-value taxonomy: **9 emitted + 2 reserved**. The first five are always emitted; the four implied-price tiers are produced only when the dbt var `enable_quality_outliers` is `true` (on in prod); and two **reserved** auto-fill tiers (`INFERRED_QUANTITY` / `INFERRED_VALUE`) are accepted-but-absent — no Gold rule emits them yet (always 0), reserved for a future auto-fill pipeline. The custom dashboard renders the pt-BR labels shown (see its "O que significa cada flag?" legend).

| Value | UI label (pt-BR) | Meaning |
|---|---|---|
| `OK` | Normais | quantity (in any unit) **and** value, with a plausible implied price |
| `MISSING_VALUE` | Valor financeiro ausente | quantity reported but monetary value missing |
| `MISSING_QUANTITY` | Quantidade ausente | monetary value reported but quantity missing |
| `MISSING_WEIGHT` | Peso ausente | COMEX/COMTRADE only — value reported but net weight missing |
| `INCOMPLETE` | Incompleto | both missing |
| `OUTLIER_VALUE` / `OUTLIER_QUANTITY` | Valor / Quantidade atípica (válida) | high-magnitude but price-consistent — a genuinely large value, **not** an error |
| `PROBLEMATIC_VALUE` / `PROBLEMATIC_QUANTITY` | Valor / Quantidade problemática (provável erro) | implied price (value ÷ quantity) >100× or <1/100× the product median ⇒ likely typo |
| `INFERRED_QUANTITY` / `INFERRED_VALUE` | Quantidade / Valor financeiro inferido | **reserved** — a blank value that a future auto-fill pipeline would impute; no rule emits it yet (always 0) |

IBGE placeholders (`-`, `...`, `..`, `*`, `X`) are converted to `NULL` in Silver by the `safe_numeric` macro.

## Final output — `gold.gold_pevs_production`

One row per `(reference_year, state_acronym, city_name, product_code)`. Columns:

**Time / geography / product**
`reference_year`, `reference_date`, `state_acronym`, `state_name`, `region`, `city_code`, `city_name`, `product_code`, `product_description`.

**Quantities (by physical unit family)**
`family` (`massa`|`volume`|`energia`|`contagem`|`area`|`desconhecida`), `unit_native` (source label), `qty_native` (value in the native unit), `qty_base` (converted to the family's base unit), `base_unit` (`t`/`m³`/`MWh`/`un`/`ha`).
> ⚠️ **Never sum `qty_base` across families.** Every quantity sum requires `GROUP BY family` (build `q_by_family = {massa:Σt, volume:Σm³, …}` at query time). Factors come from the `unit_family_conversions` + `product_unit_factors` seeds; a unit without a conversion → null `qty_base` (curation). Monetary value remains family-agnostic and summable.

**Values by year FX (foreign zeroed pre-1994)**
`val_yearfx_brl`, `val_yearfx_usd`, `val_yearfx_eur`.

**Real values via IPCA**
`val_real_ipca_brl`, `val_real_ipca_usd`, `val_real_ipca_eur`.

**Real values via IGP-M**
`val_real_igpm_brl`, `val_real_igpm_usd`, `val_real_igpm_eur`.

**Real values via IGP-DI**
`val_real_igpdi_brl`, `val_real_igpdi_usd`, `val_real_igpdi_eur`.

**Quality / provenance**
`data_quality_flag`, `last_refresh`.

## Looker Studio — recommendations

- Connect **directly** to the `${BQ_GOLD_DATASET}.gold_pevs_production` table (not to views or a "custom query").
- Enable **BI Engine** with 1–2 GB covering the Gold dataset — it cuts latency and the cost of repeated queries.
- Suggested default filter for exploratory analyses: `data_quality_flag = 'OK'` (shown as *Normais* in the custom dashboard) — or exclude the `PROBLEMATIC_*` tiers to drop likely typos while keeping the valid `OUTLIER_*` giants.

## Structure

Full folder structure (file by file) in [`ARCHITECTURE.md`](ARCHITECTURE.md#folder-structure).

> Auxiliary tooling (environment setup, IAM scripts) is in [`scripts/README.md`](scripts/README.md).

## Future transfer to the company

See [docs/ownership_transfer.md](docs/ownership_transfer.md). Nothing is hardcoded — just a new `.env` and the first run of `uv run embrapa ingest all` recreates the entire infrastructure (bucket, datasets, tables) in the new GCP project.

## Cost safety

**One-time** settings in the Cloud Console (budget alert + custom quota) that protect against unexpected charges are in [docs/cost_safety.md](docs/cost_safety.md). Recommended **before** enabling BI Engine.

---

## 📚 Documentation

| Document | Description |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Guide for AI assistants (commands, architecture, skills) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture — stack, folder structure, data flow |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide — commits, branches, PRs |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [Roadmap (Google Drive)](https://docs.google.com/document/d/1UByZ_THIJcqtYizZWrOSDsMpM_XCptj0f29VcymcPXE/edit?usp=sharing) | Project vision & evolution tracking — maintained outside the repo for business leadership (replaces `ROADMAP.md` + `TODO.md`) |
| [SECURITY.md](SECURITY.md) | Security policy and vulnerability reporting |
| [PLANS/](PLANS/) | Detailed plans for complex features |

<details>
<summary>Detailed documentation (docs/)</summary>

| Document | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Complete environment setup guide |
| [docs/auth_architecture.md](docs/auth_architecture.md) | Authentication architecture (Chain of Trust) |
| [docs/iam_setup.md](docs/iam_setup.md) | IAM and Service Account setup |
| [docs/cost_safety.md](docs/cost_safety.md) | Budget alerts and quotas |
| [docs/testing.md](docs/testing.md) | Testing strategy and guide |
| [docs/ownership_transfer.md](docs/ownership_transfer.md) | Company transfer checklist |
| [docs/looker_studio_setup.md](docs/looker_studio_setup.md) | Looker Studio → Gold connection |
| [docs/gold_data_model.md](docs/gold_data_model.md) | Gold ER diagram + join guide (tables, dims, marts) |
| [docs/frontend_data_contract.md](docs/frontend_data_contract.md) | Gold → frontend snapshot data contract (handoff) |
| [docs/operations_runbook.md](docs/operations_runbook.md) | Occasional prod ops: curators, IAP audience, curation activation, Gold backups |
| [docs/comtrade_world_backfill.md](docs/comtrade_world_backfill.md) | UN Comtrade world/all-reporters full-history backfill runbook |
| [docs/adding_a_data_source.md](docs/adding_a_data_source.md) | How to add a new data source (registries, Bronze/Silver/Gold) |
| [docs/migration_history.md](docs/migration_history.md) | Migration history |
| [scripts/README.md](scripts/README.md) | Auxiliary scripts documentation |

</details>

---

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).

Developed by [Igor Florentino](mailto:igorlopesc@gmail.com).
