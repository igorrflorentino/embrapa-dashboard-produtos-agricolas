# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

Remediation of the 2026-06-24 post-v1.6.0 deep audit (report:
`docs/audits/deep_audit_2026-06-24_v1.6.0.md`; grade A−, 0 critical). All confirmed findings
(1 high, 4 medium, 3 low) fixed; 915 pytest / 267 vitest green.

### Fixed
- **`deploy.sh` no longer disables the feedback GitHub loop on redeploy (audit INFRA-1).**
  `FEEDBACK_GITHUB_REPO` is now in the env allowlist and the `FEEDBACK_GITHUB_TOKEN` secret is
  mounted via `--set-secrets` when it exists, so a routine `make webapi-deploy` keeps the loop
  active (it was silently dropping both before).
- **Feedback is written to BigQuery BEFORE the GitHub forward (audit FB-1).** The durable row
  lands first (`issue_url` NULL) and is stamped after a successful forward, so a GitHub failure
  can never orphan an issue without a log row; the docstring is corrected.
- **Curadoria freeze completed (audit FREEZE-1).** Stale `?ip=curation` / `enrich_*` deep links
  now render a neutral "Versão Futura" notice instead of the frozen editor, and the curation
  glossary section is hidden — the app is fully decoupled from curation, even via direct URL.
- **No dev-vs-prod JSX-runtime divergence (audit DEV-1).** The classic JSX runtime is now used
  in dev, build AND Vitest (`vitest.setup.js` supplies the global `React`), so all three
  exercise the same compilation path instead of dev-only-classic vs build/test-automatic.
- **Feedback message is fenced in the GitHub issue (audit SEC-1)** — no Markdown / @-mention
  injection — and a **per-author cooldown** debounces double-clicks/abuse (audit SEC-2,
  `FEEDBACK_COOLDOWN_SECONDS`, default 5s, returns 429).

### Added (tests)
- Coverage for the GitHub-forward success path, the FB-1 write-then-stamp ordering, the SEC-1
  fence, and the SEC-2 cooldown (audit TEST-1).

### Docs
- Operations runbook + `.env.example`: the feedback `FEEDBACK_GITHUB_*` Secret Manager wiring +
  the fine-grained `issues:write` token guidance (audit DOC-1).
- Completed the 2026-06-24 deep audit (`docs/audits/deep_audit_2026-06-24_v1.6.0_complete.md`):
  confirms every fix above holds, corrects a stale `CLAUDE.md` line that called the **frozen**
  Curadoria "activatable" (audit DOC-2), and records the **live prod grain + conservation
  re-check** (audit DATA-1) — all 7 Gold tables grain-unique, `gold_source_metadata` ties exactly
  to the facts (e.g. comtrade 2,294,874 rows), and the COMTRADE World-partner double-count guard
  holds (0 rows).

### Changed
- **`deploy.sh` preserves prod-only env across routine deploys.** A new git-ignored
  `deploy/webapi/.env.prod` (template: `deploy/webapi/.env.prod.example`) is layered on top of
  the repo-root `.env` (same allowlist; prod values win), so `IAP_AUDIENCE` and
  `FEEDBACK_GITHUB_REPO` — which don't belong in a dev/worktree `.env` — are applied on every
  `make webapi-deploy` instead of being silently dropped. This removes the image-only-deploy
  workaround and keeps the in-app IAP JWT verification + the feedback cooldown armed. With
  Curadoria frozen, the feedback channel (`submitted_by`) is now the live consumer of
  `IAP_AUDIENCE`.

## [1.6.0] — 2026-06-24

Headline release of the 2026-06-24 work: the **in-app feedback channel** ("Reportar problema" →
append-only BigQuery log + IAP author + optional best-effort GitHub-issue loop), **roadmap management
moved to Google Drive** (`ROADMAP.md` / `TODO.md` retired), the **Curadoria feature frozen** (deferred
to the "Versão Futura" roadmap phase, hidden from the UI), and the **rolldown-vite dev server repaired**
(`npm run dev` was blank-screening on a CJS `require` the dev server didn't rewrite to ESM). Plus the
second-pass remediation of the 2026-06-23 **post-release audit** of v1.5.3 (15-dimension,
adversarially-verified; 37 confirmed findings) and a focused deduplication sweep. Validated:
910 pytest / 267 vitest green; ruff+format+eslint clean; `vite build`, `dbt parse`, `dbt compile`
and `sqlfluff` clean.

### Fixed
- **CAGR ("CAGR a.a.") no longer inflated for series with internal year gaps.** Both
  ViewProductCompare AND ViewCrossSource annualized over the array length instead of the
  calendar-year span; per-product series are ragged (the backend emits only existing
  `(code, year)` rows), so a gapped window overstated the rate. Both now derive the period from
  the year span via a shared `window.spanYears` helper.
- **The "Valor e volume" view no longer blanks on auto-scaled stacked composition.** Its
  per-year stack total was computed by array index across ragged product layers, throwing a
  `TypeError` (or silently dropping tail years). Now aggregates by year via `window.stackYearMax`.
- **The composition Donut renders a visible ring for a single 100% slice** (a full-circle SVG
  arc collapsed to a blank ring — the common single-product selection).
- **Sub-UF/município IBGE ingestion robustness:** the IBGE-1 deadline fix had saturated every
  per-state retry budget to the 600s drain ceiling; the retry budget is now decoupled (geo-scaled
  drain CAP, request-volume retry budget), so one slow state can't eat the nightly task timeout.
- **dbt:** the `commodity_crosswalk` seed now pre-accepts `'ppm'` (the documented PPM-linkage step
  no longer hard-fails `dbt build`); `comtrade_cpc_value` pins the `mot/mos/partner2` breakdown
  axes like Silver (no double-count); the flow-market "current" read breaks `edited_at` ties on
  `change_id` deterministically.
- **Local safety hook:** the `mkfs` guard now blocks `mkfs.ext4`/`mkfs.xfs` (a `\\w` regex typo let
  the only form anyone types through), and the dbt-prod guard no longer false-positives on
  `--full-refresh --target prod` flag order.

### Changed (security / hardening / internal)
- **Cost guard:** the product-basket `codes` IN-list is now capped symmetrically with `cityCodes`
  (`_MAX_BASKET_CODES`), via `_csv_param` (SEC-1).
- **Promoted the COMTRADE single-year invariant from `assert` to an unconditional raise** (survives
  `python -O`).
- **Deduplication** (each behaviour-preserving + verified): a shared `annual_deflation_ctes()` dbt
  macro replaces the FX+inflation CTE block copied across the four Gold models (−243 lines; compiled
  SQL proven byte-identical via offline `dbt compile` + normalized diff); `resolve_clients` /
  `resolve_bq_client` now own client construction (was inlined in 5+ sites); a `magnitude.js`
  kernel + `window.scaleLabel` end the bi/mi/mil ladder + currency-label grammar duplication; an
  `EmptyCard` atom replaces three copied empty-states. PAM/PPM now wire the `product_unit_factors`
  override like PEVS (inert today — uniform behaviour).
- **Docs/parity sweep:** COMTRADE coverage start year reconciled to 1989 in both filter hints;
  `webapi/registries.py` gains the PPM `herd` capability + `rebanho` view; `contracts.js`,
  `cache.py` and `.env.example` (`BQ_BANCO_METADATA_TABLE`) brought current.

### Removed
- **`ROADMAP.md` and `TODO.md` retired from the repo.** Project vision and evolution tracking now
  live in a Google Drive document maintained for business leadership (a simpler, render-friendly
  view for non-technical stakeholders). The doc map in `README.md` / `CLAUDE.md` points there;
  `PLANS/` (engineering specs) stays in-repo and `CHANGELOG.md` remains the canonical per-version
  record of what shipped.

### Changed (product / scope)
- **Curation/enrichment ("Curadoria") frozen — deferred to the "Versão Futura" roadmap phase.**
  Per leadership decision, the partially-built, not-yet-validated data-curation feature (the per-code
  industrialization + market-nature editor and its two curated analyses) is now HIDDEN from the
  dashboard UI: the "Análises curadas" perspectives (`frontend/src/ui/views.js`) and the "Engenharia
  de atributos" sidebar editor (`AppShell.jsx`) are commented out behind FROZEN banners. The app runs
  100% decoupled from it; the backend routes, serving writers, and the SCD2 dbt view (already gated by
  `enable_curation`, default false) are kept in place + tested as the scaffold for the real future
  implementation, each marked with FROZEN comments. The operations runbook now warns against prod
  activation while frozen. No data or behaviour change for any active view.

### Added
- **In-app feedback channel ("Reportar problema").** A new dashboard button opens a modal
  (bug / dúvida / sugestão) that POSTs to `/api/feedback`; the report is written to an
  append-only `feedback_log` BigQuery table, with the author captured from the IAP identity
  and reproduction context auto-attached (the permalink to the current view/filters, app
  version, optional user-agent). When `FEEDBACK_GITHUB_REPO` + `FEEDBACK_GITHUB_TOKEN` are
  set, each report ALSO opens a GitHub issue (best-effort — a failure never blocks or loses
  the BigQuery write); unset = BigQuery-only. Reuses the curation append-log + IAP-author
  pattern. (`serving/feedback.py`, `webapi/routes.py`, `frontend/src/ui/FeedbackModal.jsx`,
  `frontend/src/data/feedback.js`.)

### Added (tests)
- Regression tests for the ragged-series fixes (`cagrPct`/`spanYears`/`stackYearMax`, single-slice
  Donut), the `_MAX_MUNICIPIO_CODES`/`_MAX_BASKET_CODES` caps, the n6 retry-budget decoupling, the
  dbt `change_id` tiebreaker + breakdown pins, and `scaleLabel`.
- **First automated coverage for `scripts/`:** Node `--test` cases for the safety-hook regexes (wired
  into CI) and a fixture test for the IBGE municipal mesh-seed generator (`_row()`).

---

## [1.5.3] — 2026-06-23

Remediation of the 2026-06-23 **full-codebase audit** (13-dimension, adversarially-verified;
report at `docs/audits/full_codebase_audit_2026-06-23.md`). Baseline health was already A− with
0 critical issues; the changes below close 2 displayed-number HIGHs, a cluster of geography-feature
gaps, and routine hardening.

### Fixed
- **The UN Comtrade banco no longer sums the whole world's trade for 2022-2023.** Its own
  overviewTS + productTS read the multi-reporter `serving_comtrade_annual` mart WITHOUT pinning a
  reporter, so for the all-reporters backfill years the "Valor total" KPI and the value/volume
  series conflated every country's trade (a large spurious jump at 2022). Both readers now pin
  `reporter = Brazil`, matching the already-correct partner/flow/cross-source readers. (audit NUM-1)
- **Sub-UF / município geography filters now survive Compartilhar / Citar.** The five v1.5.2 geo
  dimensions were missing from the share-link codec, so a cited panel silently dropped the
  territorial narrowing; they now round-trip through the URL (and `urlDecodeNum` rejects a malformed
  numeric param instead of propagating `NaN`). (audit RVC-1)
- **The Geography "Município" granularity panel shows real data.** It rendered an always-empty
  legacy list (no backend producer); it now ranks municípios from the live município cube, with an
  honest empty-state, and the button is hidden for UF-only trade bancos. (audit GEO-1)
- **Value/Volume and Concentration views no longer flash a basket-dropped figure** during the
  product × UF cube load — they honour the same `geoComboPending` guard the Overview already used.
  (audit DATA-1)
- **Ingestion robustness:** an empty/truncated COMEX download is retried as a transient instead of a
  hard chunk failure (COMEX-1); the SIDRA drain deadline scales with a state's município count so a
  dense state can't time out on a slow night (IBGE-1); the run monitor no longer crashes on a null
  scalar and stops printing a bogus `rows=0` (OBS-1/2).
- **`embrapa doctor`** backup-freshness compares fractional days, so a snapshot just past the
  threshold is correctly flagged stale.

### Changed
- **API hardening:** `POST /api/municipio-yearly` caps + type-checks `cityCodes` (a pathological or
  non-list payload is a clean 400), the app sets `MAX_CONTENT_LENGTH`, and `_json_safe` serializes
  `decimal.Decimal`. (audit SEC-1/2/4, JSON-1)
- **dbt tests:** the Gold→serving value-conservation test and the unconvertible-quantity
  curation-surface test now cover PPM and COMTRADE; `dim_geo_municipio`'s sub-UF columns are
  documented for `persist_docs`. (audit DBT-1/2/3)
- **CI / infra:** the release workflow runs a lint+test gate before publishing the prod image; the
  deploy scripts fail loudly instead of silently defaulting to `:latest`; the destructive-command
  hook now covers `gcloud run jobs` / `scheduler` / `secrets` / `iam` / `monitoring` delete.
  (audit INFRA-1/2/3)
- Documentation sweep (README / ARCHITECTURE / ROADMAP / SECURITY / dbt) to reflect IBGE PPM, the
  v1.5.2 geography feature, and the current supported version. (audit DOC-1..9)

### Security
- **Dependency CVE bumps** (`uv lock --upgrade`): cryptography 48 → 49 (the one with unambiguous prod
  reach — the TLS path to GCP), Flask 3.0.3 → 3.1.3, Werkzeug 3.0.6 → 3.1.8, pydantic-settings
  2.14.1 → 2.14.2, msgpack 1.1.2 → 1.2.1. The remaining advisories in the set were present in the
  lockfile but not reachable in this codebase.

---

## [1.5.2] — 2026-06-23

The **IBGE sub-UF geography** feature (shipped in #157 but previously undocumented) plus
two rounds of audit remediation: the 2026-06-22 quality audit (11 findings — see
`docs/audits/quality_audit_2026-06-22.md`) and a 2026-06-23 manual-scan follow-up on the
freshly-shipped geo code (3 edge-case robustness bugs). Security core re-confirmed clean.

### Added
- **Sub-UF geography + live município filter (IBGE municipal mesh).** The geography filter
  now offers the IBGE territorial levels BETWEEN UF and município — BOTH parallel divisions:
  classic **mesorregião → microrregião** and 2017 **região intermediária → imediata** — plus
  **município** as a live filter. Backed by a new `ibge_municipio_mesh` seed (~5570 municípios
  → both divisions; refreshed by `scripts/refresh_ibge_municipio_mesh.py`), the conformed
  `dim_geo_municipio` dim, a município-grained serving cube read straight from Gold
  (city-scoped + `maximum_bytes_billed`-guarded), and two BFF routes: `GET /api/geo-mesh`
  (the cascade universe) + `POST /api/municipio-yearly` (the basket + city-scoped cube). The
  cascade engine reconciles two parallel sub-UF branches with a "following" refill (re-selecting
  a parent restores its children). Applies to the municipality-grained IBGE bancos
  (`ibge_pevs`/`ibge_pam`/`ibge_ppm`); COMEX (UF-origin) / COMTRADE (international) are unaffected.

### Fixed
- **The Geography view now honours the flow filter for a COMEX product basket.** The
  basket-scoped `/api/geo-yearly` cube dropped the active export/import direction (while
  the snapshot applied it), so VALOR TOTAL + the choropleth showed all-flows figures,
  internally inconsistent with the flow-filtered rest of the app. `flow` now threads the
  frontend cache key + request → `/geo-yearly` → `seam.geo_yearly` → the gateway reader
  (which already applied it). (audit M2)
- **`ingest reconcile` now covers the PAM and PPM SIDRA sources.** The old-year
  upstream-revision escape hatch skipped every `in_all=False` source, so a correction to
  an old PPM (live) or PAM year was never re-queried; reconcile now re-fetches them
  `--full` alongside BCB/COMEX (COMTRADE stays excluded, key-gated). (audit M1)
- **UN Comtrade daily-quota exhaustion exits 0, not 1.** Quota is expected and
  self-healing (the next scheduled run resumes), so it no longer trips the Cloud Run
  job-failure alert; a genuine non-quota chunk failure still exits 1. (audit L6)
- **`fetch_banco_metadata` now honours `CACHE_CLASSIFICATION_TIMEOUT`.** It was the one
  curation-class read left pinned at the decoration-time default, contradicting its own
  "a Console maturity flip reflects within the window" contract. (audit L8c)
- **The município cube is requested via POST, so a broad sub-UF selection no longer 414s.**
  A wide narrowing (e.g. most mesorregiões of a large UF) resolves to thousands of city codes;
  sent in a GET query string they overflowed gunicorn's request-line limit (~4 KB → HTTP 414).
  They now travel in the POST body, and a non-empty city set is required — so the backend never
  scans the full ~146k-row município grid. (audit 2026-06-23 A/D)
- **An empty sub-UF selection reads as honest "no data", not an eternal spinner.** A
  legitimately-empty município cube (`[]`) was conflated with not-yet-loaded (`null`), pinning
  the view at a permanent loading state; an empty result also no longer silently falls back to
  the all-UF grid (which showed data the selection excludes). (audit 2026-06-23 B)
- **A not-yet-built `dim_geo_municipio` degrades to an empty payload, not a 500.** The geo
  readers now catch `NotFound` (mirroring `banco_metadata_overrides`), so a fresh/dev/PEVS-only
  environment returns `{municipios: []}` instead of 500-ing the whole geography menu — matching
  the documented contract. (audit 2026-06-23 C)

### Changed
- **pre-commit ruff pinned to v0.15.13** (was v0.6.9), matching the ruff CI runs, so the
  local hook can't format/lint differently than CI. (audit L1)
- **Dependabot now watches the Docker base images** (`deploy/webapi`, `deploy/ingestion`)
  so a `python:3.12-slim` / `node:22-slim` CVE surfaces as a PR. (audit L2)
- **`__version__` reads from package metadata** and `pyproject` version bumped to `1.5.1`
  (was a stale `1.0.0`; `__init__` was `0.1.0`). Nothing user-facing read either —
  cosmetic. (audit L3)
- **A warn-severity `not_null` test on the curation `edited_by` author** closes the one
  untested column on the SCD2 audit trail. (audit L8b)
- **`sa-secret-reader-prod` dev-workflow grant doc corrected** to `roles/bigquery.user`
  (matching the permission matrix + the ps1 grant script; the walkthrough said
  `jobUser`). (audit L7)

### Docs
- Added IBGE PPM to the ARCHITECTURE folder/model/scheduler trees, the `doctor` sample in
  `docs/testing.md`, and the dataset list in `docs/ownership_transfer.md` (PPM has been
  live since v1.3.0 but was missing from these). (audit L4)
- Documented the one accepted long-lived SA key (`sa-claude-code-web-dev`) + a 90-day
  rotation reminder in `SECURITY.md` / `docs/auth_architecture.md` (both previously
  claimed "no long-lived keyfiles"). (audit L7)
- Noted that editing a seed an incremental model consumes needs `--full-refresh`
  (silver_ibge_pevs header + the dbt-workflow skill). (audit L8a)
- **Documented the sub-UF geography feature across the living docs** (ARCHITECTURE,
  `docs/gold_data_model.md`, `docs/frontend_data_contract.md`, CLAUDE.md, `scripts/README.md`) —
  it had shipped in #157 with only a `PLANS/` entry. Added a cross-source `dim_geo_municipio`
  vs `dim_geo_br` UF→região consistency test. (audit 2026-06-23 docs)

---

## [1.5.1] — 2026-06-21

Hardening pass on the new **"Dados (tabela)"** raw-table endpoint, from a security-weighted
adversarial audit (40-agent sweep). The audit **confirmed the security core holds** — no SQL
injection, no arbitrary-table read past the `(banco, table)` allowlist, no cache exhaustion —
so this release is robustness + correctness on the same surface, not a vulnerability fix.

### Fixed
- **Malformed filter input now returns a clean `400`, never an opaque `500`.** A missing/`null`,
  non-numeric, non-finite (`inf`/`nan`), or non-scalar (list/dict) filter value used to raise a
  bare `TypeError`/BigQuery error that fell through to the 500 handler (with a spurious
  "Unhandled error" log). `serving/sql._coerce_filter_value` + `webapi/routes._parse_table_filters`
  now reject these as `ValueError → 400`.
- **Filtering a `DATE`/`TIMESTAMP` column works.** Such a column bound its value as `STRING`,
  so `last_refresh = <string>` was a BigQuery type mismatch → 500. The comparison now runs
  against `CAST(col AS STRING)` (verified on prod: `reference_date`/`last_refresh` filters
  on `gold_pevs_production`).
- **NULL in an `INTEGER`/`BOOLEAN`/`DATE` column no longer 500s the page.** BigQuery surfaces
  these as pandas `pd.NA`/`pd.NaT` (not float `NaN`); the JSON encoder rejected `pd.NA` and
  `pd.NaT.isoformat()` leaked the literal string `"NaT"`. `webapi/app._json_safe` now maps both
  to JSON `null`.
- **`contains` filter matches literally.** It used `LIKE '%val%'` with no wildcard escaping
  (BigQuery `LIKE` has no `ESCAPE` clause), so a value with `%`/`_` over-matched. Now uses
  `CONTAINS_SUBSTR` (bound literal needle; verified on prod: `'%'` matches 0 rows, not all).
- **Transient `400` flash on banco switch removed.** `ViewDados` now gates the rows fetch on
  `tableBanco === database`, so it won't request the previous banco's table mid-switch.

### Security / cost
- **Tighter per-request byte cap for raw-table queries** (`RAW_TABLE_MAX_BYTES` = 10 GiB, vs
  the 100 GiB global guard) — defense-in-depth for a raw-data endpoint, while still allowing a
  full sort of the largest Gold table.
- **No internal attr on the wire** — the `/api/tables` payload dropped the dead `dataset`
  field (it leaked an internal config-attr name and the frontend never used it).

### Tests / docs
- End-to-end allowlist-rejection route test (out-of-allowlist `(banco, table)` → `400` through
  the real route→seam→gateway, no BigQuery), filter-coercion `400` tests, `_json_safe` NA/NaT
  test, `CAST`-comparison + `CONTAINS_SUBSTR` SQL tests, non-scalar-value `400` test, and a
  banco-switch render test. **868 pytest / 231 vitest green.**
- `/api/tables` + `/api/table` added to the canonical endpoint table in
  `PLANS/react_migration_contract_map.md`.

---

## [1.5.0] — 2026-06-21

New **"Dados (tabela)"** perspective on every banco — a faithful, unsummarized window onto
the actual rows so researchers can verify data line-by-line or hunt a value they suspect is
wrong. Preview-verified on real production data (2,4 mi linhas de `gold_ppm_production`).

### Added
- **Tabular data-inspection view** (`frontend/src/ui/ViewDados.jsx`, in the "Documentação
  do banco" group, universal). Per banco it lists the **principal (Gold) table + the serving
  marts that feed its charts** (so the derived tables are inspectable too), and for the
  selected table browses the RAW rows with **server-side pagination, ordenação (clique no
  cabeçalho) e filtros por coluna** (=, ≠, >, ≥, <, ≤, contém, é nulo) + **exportação do
  recorte em CSV** (até 500 linhas).
- **`/api/tables` + `/api/table` endpoints** (`webapi/routes.py` → `seam` → `gateway` →
  `serving/sql.py`). Security + cost by construction:
  - **(banco, table) allowlist** (`gateway._INSPECT_TABLES`) — only a banco's own Gold +
    serving marts; any other table → HTTP 400 (no arbitrary-table reads, no Silver/Bronze).
  - **The table's live schema IS the column allowlist** — ORDER BY / filter columns are
    validated against `client.get_table().schema`; filter VALUES stay bound `@params`.
  - **Hybrid read**: a plain browse uses the FREE `tabledata.list` (no bytes billed); only
    an actual sort/filter spends a query, capped by `BQ_MAX_BYTES_BILLED`. Page size capped
    at 500 rows.

### Tests
- `ViewDados.test.jsx` (picker + grid + empty state); `serving/sql.raw_table_*` (column
  allowlist, bound filters, limit cap, bad-op/value rejection); `gateway` allowlist boundary;
  `serialize_table_page`; the `/api/tables` + `/api/table` routes (arg + filter-JSON parsing,
  400 on malformed). **863 pytest / 230 vitest green; eslint + ruff clean; build OK.**

---

## [1.4.2] — 2026-06-21

Audit remediation. A post-feature adversarial sweep (45 agents) found that making the
herd value-aware in 6 views still left the **same value-assumption bug class** in code
paths not touched by `1.4.0`/`1.4.1`: a herd basket (a value-less stock) silently
rendered R$ 0, empty maps, or wrong exports. Preview-verified on real production PPM data.

### Fixed
- **`dataFilters` cube path dropped `q_count`** — once a product-subset loaded the geo
  cube, the herd's geographic Gini/HHI/Lorenz collapsed to all-zero (the snapshot path
  kept it; the cube path didn't). `regionData` likewise now carries `q_count`.
- **Overview "Quantidade · Contagem" KPI blended incompatible quantities** — it summed
  ~68 bi eggs (a flow) + ~1.9 bi heads (a stock) across 8 non-additive species into one
  meaningless headline on PPM's default view. It is now **suppressed when the basket
  contains a stock**, with a note pointing to the per-species **Rebanho** view; the geo
  digest map + "UFs cobertas" counter read headcount for a value-less basket.
- **`ViewGeography` was herd-blind** — it now offers a **"Quantidade (cabeças)"**
  dimension (with a não-somar-entre-espécies caveat) instead of an all-zero Valor map;
  `value` is gated on having value so a herd defaults to cabeças.
- **`ViewValueVolume` showed R$ 0** for a herd — the monetary cards are gated on having
  value, with an honest note redirecting a herd basket to Rebanho.
- **CSV export** — added a `qtd_contagem_un` column to the aggregate/geo/concentration
  exports, and fixed the per-product export that **mislabelled a headcount as tonnes**
  (`fam==='volume'?…:t`) and scaled it 1000× wrong; now a family→unit map.
- **`ViewProductProfile` "Participação no efetivo"** denominator no longer blends the
  herd stock with egg/milk count-flows (a stock's share is among other stocks).
- **`serialize_products_by_uf`** now emits the `q_count` its SQL already computed (was a
  dead column), so 'Produtos do estado' can rank a herd by headcount.

### Changed / docs / tests
- `ViewProductCompare` titles the normalized chart "do efetivo (cabeças)" for an all-herd
  basket (was hardcoded "do valor"); `overviewTS` contract + `serialize_geo_yearly`
  docstring corrected; `frontend_data_contract.md` documents `measure_kind`/`q_count`;
  added the missing `.qa-facet` CSS.
- New lock-in tests: `serialize_product_uf` + `serialize_products_by_uf` q_count,
  ViewConcentration cabeças fallback, ViewOverview count-KPI suppression, `pearsonByYear`
  `key='q'`. **854 pytest / 228 vitest green; eslint + ruff clean; build OK.**
- **Baseline health stayed excellent** (96% backend coverage, sql.py 100%, max CC C(12)
  pre-existing, MI all A); security review confirmed **no new injection/SSRF/auth-bypass**.

---

## [1.4.1] — 2026-06-20

Refinement to the livestock herd feature (`1.4.0`), preview-verified end-to-end against
the local webapi on real production PPM data (composição Galináceos 82% / Bovino 12%, UF
líder PR; Perfil stock=Bovino mostra efetivo 238 mi cab sem Valor/Preço).

### Added
- **Stock/flow facet on the Qualidade view** — for a banco carrying `measure_kind`
  (livestock), the per-product data-quality breakdown splits into **Estoque** (the herd —
  value-less, so its flags are OK vs quantidade-ausente) and **Fluxo** (animal products —
  value + quantity). The two have structurally different flag profiles, so one merged list
  blurred the diagnosis.

### Changed
- **Overview count KPI relabelled** `Efetivo/contagem` → **`Quantidade · Contagem`** — the
  KPI sums the herd (a stock) AND eggs (a flow), so "Efetivo" overclaimed; the neutral
  label is consistent with the Massa/Volume quantity KPIs.
- **`vite.config.js`** — a `preview` proxy now mirrors the dev `/api` proxy, so a production
  build can be smoke-tested against the local webapi (`npm run preview`). Used to
  preview-verify this change: the experimental rolldown-vite **dev** server mishandles the
  injected JSX runtime ("require is not defined"), so the **build** preview is the reliable
  local-verification path.

---

## [1.4.0] — 2026-06-20

Makes the **IBGE PPM herd visible**. The livestock headcount — ~⅔ of
`gold_ppm_production`, the largest single body of rows the new banco added — was
structurally invisible as a quantity (every chart showed `q: null` for it). This
release gives `contagem` its own quantity track end-to-end and adds a dedicated
**Rebanho** perspective; no Gold rebuild (the headcount was already in `qty_base`).

### Added
- **New perspective: "Rebanho"** (`frontend/src/ui/ViewRebanho.jsx`) — the herd
  (efetivo dos rebanhos) view, gated on a new `herd` capability that only IBGE PPM
  provides. Cabeças-only (no monetary axis): latest-year composition by species
  (donut), 50-year per-species evolution (multi-line — never stacked, since heads of
  different species are not additive) and a per-UF headcount tile map of the focused
  species, with honest "estoque, não somar entre espécies" caveats.
- **`q_count` quantity track (the keystone)** — `contagem` (livestock head + eggs) gets
  its own per-family `qty_base` column across the serving readers (`serving/sql.py`) and
  the serializer (`webapi/serializers.py`), so the herd now renders a real quantity where
  it previously emitted `q: null`. `serialize_product_uf` also carries `q_count`, so a
  value-less stock ranks UFs by headcount instead of an all-zero value.
- **`measure_kind` (stock|flow) on the products list** — exposed PPM-only via a gateway
  flag (`with_measure_kind`), letting the UI separate the value-less herd (stock) from
  the animal-product flows (eggs/milk) that share the `contagem` family.

### Changed
- **Analytical views are now value-less-aware** — each perspective implicitly treated
  monetary `value` as the universal measure, which a stock (the herd) breaks. **Perfil
  do produto** swaps Valor/Preço for Efetivo/Pico and ranks UFs by headcount for a stock;
  **Visão geral** adds an efetivo KPI; **Comparativo** indexes (base 100) and correlates
  a herd on headcount instead of a flat-zero value line; **Concentração** falls back to
  cabeças (Gini/HHI/Lorenz) for a value-less basket.
- **Count formatters + unit registry** — new `formatCountQty`/`countQtyMul`/
  `countAxisLabel` (mirroring mass/volume); `UNIT_FAMILIES` re-keyed `contagem`→`count`
  to match the token the serializer emits — a latent mismatch that was dormant until the
  first count-family product rendered a quantity.

### Tests
- New `ViewRebanho.test.jsx` (herd built from stock species only; cabeças-only
  composition/evolution; honest empty state) + a count-KPI lock-in in
  `ViewOverview.test.jsx`; serializer + `sql.products`/`product_timeseries` gain
  `q_count`/`measure_kind` coverage. **853 pytest / 223 vitest green; eslint + ruff
  clean; vite build OK.**

---

## [1.3.0] — 2026-06-20

New dashboard banco **IBGE PPM** (livestock), now **LIVE in production**, plus a SIDRA
ingestion-robustness fix that unblocked its historical backfill.

### Added
- **New data source: IBGE PPM** (Pesquisa da Pecuária Municipal) — a new dashboard
  banco `ibge_ppm` for livestock: herd headcount (SIDRA 3939, Cabeças) + animal
  production (SIDRA 74 — leite/ovos/mel/lã, with value). PPM is **multi-table**
  (a first for the SIDRA sources): one `ingest ibge-ppm` ingests both tables into
  two Bronze tables, unioned in `silver_ibge_ppm` with a `measure_kind` (stock|flow)
  discriminator. New `gold_ppm_production` (no área/yield — livestock) + serving mart
  `serving_ppm_annual` ride the full deflation/FX matrix and the PEVS-shaped gateway
  readers with no new query SQL. Capability-wise PEVS-shaped (`provides` product/geo/
  quality, **no** produtividade). New `PPM_*` knobs + `BQ_BRONZE_PPM_{HERD,ANIMAL}_TABLE`;
  excluded from nightly `ingest all` (annual) — on-demand via `ingest ibge-ppm` + the
  monthly `schedule_ppm.sh` (cron `0 4 3 * *`). New unit_family_conversions seed rows
  fold the SIDRA ×1000 "Mil litros"/"Mil dúzias" scale. **Activated 2026-06-20**:
  Bronze backfilled 1974→2024 (2.27M herd + 3.41M animal rows) via the Cloud Run Job,
  Gold/serving built (2.4M-row `gold_ppm_production`, all dbt tests green on prod data),
  and the `banco_metadata` maturity set to `beta`.

### Changed
- **Volume-based dynamic SIDRA timeout + jittered exponential backoff** (#148) — the
  flat 75s per-request drain budget was too tight to stream a wide-window / many-product
  IBGE response when SIDRA is slow (it killed the PPM backfill: a cell-halved 13y ×
  8-product query for a big state couldn't drain in 75s, and a slow-byte timeout — unlike
  a cell-limit error — never triggered further halving). The drain + retry budgets now
  scale with the request's period×product×variable volume (above the lean floor, clamped
  to a ceiling), and `http_retry_policy` uses full-jitter exponential backoff to
  de-synchronise the parallel state-fetch workers. Shared by IBGE/BCB/COMEX.

---

## [1.2.0] — 2026-06-19

Capability-aware UI: the dashboard now surfaces **only what each data source can
actually do** — across the single-banco filter menu, the multi-fonte perspectives,
and the cross-source pickers — so the screen is never cluttered with options that
lead nowhere. Plus a leaner analytical bundle and a dead-code/doc sweep. No data or
mart-grain change — the new code runs against the existing prod Gold/serving tables.

### Added
- **Dynamic, capability-gated filter menu** (#143) — every filter option now loads
  from a per-banco schema (`FILTER_SCHEMAS`): a dimension appears only when the active
  banco provides it, instead of always-on filters that silently no-op. The **Fluxo**
  segment (exportação/importação) became a real **server-side** filter — it re-fetches
  the snapshot scoped to the chosen flow (the marts already carry `flow`; no dbt change).
- **Capability-gated multi-fonte perspectives** (#144) — the cross-source perspective
  picker now **disables** (with a "Demonstração" badge + reason) the perspectives whose
  source does not exist yet (`cross_chain`/`cross_lag` — they need SEFAZ inter-UF flows /
  monthly PEVS), via a new `crossViewApplies` gate (data-blocked / source-availability /
  ≥2 comparable series). The cross-source **series picker** hides banco cards with no
  comparable metric (PAM) and disables the chips of metric-but-no-data bancos (SEFAZ).
- **Family-gated commodity pickers** (#145) — the **Coeficiente de exportação** and
  **Preço: porteira vs. FOB** views (which compare PEVS mass to COMEX weight) now offer
  ONLY pure-mass commodities and open on a real indicator, instead of defaulting to the
  always-incompatible "Cesta completa". `/api/catalog` now carries each commodity's PEVS
  `family` (derived from the existing `_pevs_family_by_commodity` index).

### Changed
- **Leaner analytical bundle** (#141) — the audit-polish pass trimmed the Plotly
  payload, raised `webapi` test coverage, and documented `PYTHONUTF8=1` for local dbt
  on Windows (cp1252 crash fix).
- **Dead-code & doc-staleness sweep** (#142) — removed backend + frontend orphans,
  wired the dormant `contracts.js` runtime contract-lint, and fixed 5 stale docs;
  0 synthetic-data leftovers remain.

---

## [1.1.0] — 2026-06-19

Full remediation of the 2026-06-18 repository audit (#138) — **0 critical / 0 high**;
the focus was displayed-number correctness, plus security/robustness hardening and
test coverage. Verified live in production (dashboard reads + curation writes).

### Added
- **Security hardening** — `current_author()` fails CLOSED on Cloud Run without
  `IAP_AUDIENCE` (refuses to stamp a forgeable curation author); `deploy/webapi/deploy.sh`
  hard-fails post-deploy if `invoker-iam-disabled=true` or `iap-enabled≠true`; the
  `release.yml` `version` input is env-indirected + validated. New `embrapa doctor`
  **`currency-codes`** probe guards `BCB_CURRENCY_SERIES` against a stale-`.env` FX
  regression.
- **dbt numeric + grain tests** — a deflation/FX `unit_test` on `gold_pevs_production`
  (the scientific core, previously untested numerically; validated on BigQuery),
  uniqueness tests on the `silver_bcb_inflation`/`silver_bcb_currency` grain, and an
  `if: failure()` stale-marts alert on the nightly prod build.
- **Test coverage** — `serving/gateway.py` 80% → 99% (parametrized reader-wiring
  tests), frontend View render tests (ViewQuality/Overview/Concentration), and
  nested snapshot-contract drift detection.
- **Dependabot** now also covers the `pip` (Python) and `npm` (frontend) trees.

### Changed
- **ESLint now lints `frontend/src/ui/`** (the live production UI), fixing the
  previously-hidden dead code, stale `eslint-disable` directives, and hook deps.
- **Sidebar + modal accessibility** — sidebar items are keyboard/screen-reader
  operable (role/tabindex/Enter), and the filter + citation modals close on Escape
  with `aria-modal`.
- **`v1.1.0` deployed** — `IAP_AUDIENCE` is now set on the prod Cloud Run service, so
  curation uses the cryptographic IAP-JWT verification (no longer the spoofable
  plaintext header).

### Fixed
- **Quality-flag taxonomy** — the frontend registry now matches the real Gold flags
  (`OK/MISSING_VALUE/MISSING_QUANTITY/MISSING_WEIGHT/INCOMPLETE`). The stale prototype
  taxonomy was silently dropping `INCOMPLETE`/`MISSING_WEIGHT` from the Quality view +
  filter and leaking raw English ids in place of the pt-BR labels.
- **Physical-quantity scaling** — `product_timeseries` emits per-family base sums
  (`q_mass`/`q_vol`) so mass and volume are never blended and count/energy/area
  quantities are no longer mis-scaled (no more `count ÷ 1e6`).
- **COMTRADE partner ranking + flow Sankey** pin the reporter to Brazil, fixing the
  2022–2023 all-reporters multi-count.
- **COMEX freshness** — only the ETag confirms "current" (Last-Modified is too weak
  for a same-second republish); **COMTRADE** permanent truncations are logged
  distinctly (operator action required) instead of buried as a generic failure.
- **Docs** — a stale `src/proto` reference, 5 repo-escaping `../` links in
  `ARCHITECTURE.md`, the renamed curation SCD2 view/log-table names, the CONTRIBUTING
  CI-checks list, and the BCB delta-overlap granularity wording.

---

## [1.0.0] — 2026-06-18

### Added
- **Dedicated dashboard rebuilt as a React SPA + Flask REST `webapi`** (Plotly.js
  charts), replacing the Dash UI entirely — served from one origin behind Cloud Run
  direct IAP (`src/embrapa_commodities/webapi/`, `frontend/`). The Dash package was
  removed at cutover.
- **Decoupled release CI** — `.github/workflows/release.yml` (#132) builds a
  versioned, immutable `webapi` image to Artifact Registry on a `v*` tag; deploy
  without rebuild via `WEBAPI_SKIP_BUILD=1 WEBAPI_TAG=vX deploy/webapi/deploy.sh`.
  Pinned action SHAs bumped to Node-24 majors (#133). `v1.0.0` released + deployed.
- **Per-UF chart scoping + new chart metrics (P1–P6, #131)** — partner metric
  toggle (value|weight|price), OLS trendlines, value-added volume+price, and a
  dual-metric seasonality; `serving_comex_seasonality` grain now includes
  `state_acronym` (×UF).
- **UN Comtrade world/all-reporters full-history backfill runbook** —
  `docs/comtrade_world_backfill.md` (#128), with a daily Cloud Run Job scheduler.

### Changed
- **IAP-only ingress + scale-to-zero, no load balancer (#122).** The dashboard runs
  Cloud Run direct IAP (`ingress=all` + IAP, `min-instances=0`) — the zero-fixed-cost
  posture; an external HTTPS LB stays future-only / out of scope.
- **`silver_comtrade_flows` is now incremental** (`insert_overwrite` by
  `reference_year`, #127) — caps the cost of the all-reporters backfill.
- **`reconcile` is operator-triggered + a monthly reminder issue**
  (`.github/workflows/reconcile-reminder.yml`, #130) — no longer an unconditional
  scheduled run.
- **Enrichment is now a sidebar SECTION with one screen per tool** (was a single
  "Curadoria" item opening one window with internal tabs). The "Enriquecimento"
  section holds **Nível de industrialização** (`?ip=enrich_industrial`) and **Tipo
  de Mercado** (`?ip=enrich_market`), each its own screen over the same shared
  institutional store — so each enrichment can be done separately. `ViewCuration`
  split into `ViewEnrichmentIndustrialization` + `ViewEnrichmentMarketNature` with a
  shared apply bar; the old `?ip=curation` deep link still resolves (→ industrialization).
- **9-commodity scope across every source** — castanha-do-brasil, madeira, açaí,
  cupuaçu, banana, mandioca, soja, milho, arroz, each on the sources that carry it.
  Codes verified (live SIDRA, official NCM table, WCO/HS); COMEX gained a 4-digit SH
  *heading* tier in the product matcher.
- **Full historical backfill**: IBGE PAM back to **1974** (monetary reform absorbed
  via `historical_currency_factors`, was 1994+); UN COMTRADE Brazil-reporter to **1989**.
- **IBGE PAM and UN COMTRADE graduated `beta → estável`** (complete data, no caveat),
  flipped through the new editable `research_inputs.banco_metadata` override table
  (maturity/coverage edits are a BigQuery `MERGE`, merged over the registry by
  `/api/source-meta` — no rebuild/redeploy).
- **Geo filter nação restricted to Brasil** for domestic bancos: the cascade no
  longer offers foreign "export destinations" (China/EUA/…) — a prototype fabrication
  that mapped to no column in any geo-cascade banco (dead options). International
  partners stay a real dimension only for COMEX/COMTRADE, via their own país/partner
  filters.

### Fixed
- **The VALOR TOTAL hero ignored the state filter and the choropleth ignored the
  product basket** (Overview/Geografia). Both stemmed from the per-banco snapshot
  lacking a product × UF × year grain (the honest "a cesta não recorta a distribuição
  por UF" note). A new basket-scoped cube — `/api/geo-yearly`, reusing the existing
  `serving_*_annual` `*_by_uf_yearly` readers with `product_codes` (**no new dbt
  model**) — now lets the hero, choropleth, ranking and series respect **state +
  product + período together** (the note clears once the cube loads). `applyFilters`
  pulls it on demand and sums it over the selected states client-side; the value
  column matches the snapshot's via the active currency×correction.
- **Transparent retired→current code translation** — the dashboard now exposes only
  current codes, with retired-code history folded into them: `comtrade_hs_succession`
  + `comex_ncm_succession` seeds applied in the silver models (`coalesce(succ.current
  _code, code)`; raw kept in `*_code_reported`, the true natural key for the uniqueness
  tests). Verified: 0 retired codes leak to Gold.
- **Full codebase audit + live visual inspection: 117 confirmed defects resolved.**
  A two-phase audit (automated metrics + an adversarially-verified manual sweep)
  found **106 issues, all fixed** — including the three once-deferred items: the
  commodity-level curation dead-code removal, the UF/state filter wired into the
  trade flow/partner readers, and **real year-FX BRL/EUR for trade bancos**
  (retiring the frontend mock-FX rates; trade values now come from the Gold
  columns). A subsequent **live dashboard inspection** found and fixed **11 more
  UI/data issues**, most notably: the Overview/Geografia **per-UF map showed an
  all-years cumulative mislabeled as the latest year** (the per-UF readers now
  scope to the latest year, matching the national KPI and the `ano × UF` heatmap);
  a **misleading year-over-year on an incomplete latest year** (now anchored on
  the last complete year, with the partial year marked "(parcial)" on the series,
  composition donut and map — the backend exposes `monthsInLatestYear` /
  `latestYearComplete` / `latestCompleteYear` on `/source-meta`); **"UFs cobertas"
  counted COMEX pseudo-origin codes** (ND/EX/ZN…) against the 27 real states
  (ufData rows now carry a `real` flag); stale filter-summary chips; a duplicate
  `/source-meta` fetch; and the Saúde "saudáveis" denominators. Also corrected:
  the dbt 1994 `val_yearfx_*` CR$/R$ changeover, the append-only Comtrade
  `cpc_value` dedup, the quality-flag taxonomy (real Gold flags), the implicit
  price for volume-family products (1000× overstatement), and COMEX/COMTRADE mass
  quantities (kg summed and scaled as tonnes). Decomposed all radon grade-C
  functions and added ~210 tests (Python 497→701, frontend 47→103); full suite
  green. Detailed report: `docs/audits/codebase_audit_2026-06-12.md`.
- **Geografia choropleth ("Mapa" mode) rendered blank.** Confirmed in production
  (not a headless artifact): `brazilUfGeo` shipped **143 empty `[]` sub-polygons**
  inside its MultiPolygons (a shape-simplification artifact), and maplibre-gl 4.x's
  geojson-vt worker throws "Cannot read properties of undefined (reading 'length')"
  on an empty sub-polygon, dropping the ENTIRE feature → 0 features → blank map. The
  GeoJSON is now sanitized once at load (`charts/geoSanitize.js`, unit-tested) into
  valid GeoJSON, and a `map.on('error')` handler surfaces any future maplibre error
  under our own prefix. The Geografia per-UF map/bars also gained the "(parcial)"
  marker on an incomplete latest year, matching the Overview.

### Removed
- **Chinese Yuan (CNY) dropped entirely.** The dashboard now offers only BRL, USD and EUR. Removed the external-FX path that sourced BRL/CNY (the `extfx_cny_brl` seed, `silver_extfx_currency`, and `scripts/refresh_cny_seed.py`) and dropped the `val_yearfx_cny` / `val_real_ipca_cny` / `val_real_igpm_cny` / `val_real_igpdi_cny` columns from every Gold fact (`gold_pevs_production`, `gold_pam_production`, `gold_comex_flows`, `gold_comtrade_flows`). Requires a `dbt build --full-refresh` to physically drop the columns; Looker Studio reports bound to the CNY metrics must unbind them (see `docs/looker_studio_setup.md`). China-the-country trade flows (COMEX/COMTRADE partner geography) are unaffected.

### Added
- **New data source: IBGE PAM (Produção Agrícola Municipal, SIDRA table 5457)** —
  annual crop production (área, quantidade, rendimento, valor) by municipality,
  the second IBGE/SIDRA source alongside PEVS. Lean first cut: 5 highest-value
  crops (soja, milho, café, cana, arroz) from 2010, surfacing **quantidade** and
  **valor da produção** in the dashboard (área/rendimento are carried in Gold for
  a follow-up). Reuses the generic SIDRA client; new `ibge/pam_pipeline.py`
  (two-phase Bronze, own `bronze_pam` dataset + `raw/ibge/pam/` segment),
  `ingest ibge-pam` CLI (**excluded from nightly `ingest all`** — annual,
  slow-changing — runnable on demand), `doctor` PAM probe + Bronze/serving
  targets. dbt: `silver_ibge_pam` → `gold_pam_production` → `serving_pam_annual`
  (column-identical to the PEVS mart, so PAM rides the source-parameterized
  gateway readers, the currency/correction toggles, and the quality views), plus
  a Silver→Gold conservation test. Banco `ibge_pam` graduates `planejado → beta`.
  Lean assumption: the monetary value is nominal R$ via ×1000 from "Mil Reais",
  valid for the post-1994 window (`PAM_START_YEAR` ≥ 1994). New knobs:
  `PAM_TABLE_ID`/`PAM_CLASSIFICATION_ID`/`PAM_PRODUCT_CODES`/`PAM_START_YEAR`/
  `PAM_END_YEAR`/`PAM_DELTA_OVERLAP_YEARS`, `BQ_BRONZE_PAM_{DATASET,TABLE}`.
- **IBGE PEVS is now delta by default** (like the BCB). `ingest ibge` / `ingest all`
  re-fetch only from `latest_bronze_year - IBGE_DELTA_OVERLAP_YEARS` (default 1)
  forward — absorbing PEVS revisions and a newly published year — instead of
  re-pulling 1986→today on every run (a huge request that blows SIDRA's slow-byte
  deadline on an unattended Cloud Run Job). `--full` forces the full window;
  `ingest ibge-batch` remains for the initial chunked historical backfill; a cold
  Bronze falls back to the full window. New helper `latest_reference_year`
  (`gcp/bigquery.py`) + `IBGE_DELTA_OVERLAP_YEARS` knob. Motivated by a Cloud Run
  Job smoke-run that failed on exactly this IBGE full-history fetch.
- **Architectural pivot — Pushdown Computing in the dashboard (replaces the
  in-memory/Pandas design, with its OOM/concurrency risk).** The dashboard (now the
  React SPA + Flask `webapi`) is **stateless**: UI filters turn into **parameterized SQL** (`@param`) on
  BigQuery, cached by **flask-caching**, instead of loading Gold tables into memory.
  - **dbt `serving/`**: marts pre-aggregated at the chart grains
    (`serving_pevs_annual`, `serving_comex_annual`, `serving_comex_seasonality`,
    `serving_comtrade_annual`, `serving_quality_by_source`) in the `serving` dataset
    (`BQ_SERVING_DATASET`), materialized as **tables** (cutting scan from GB→MB).
  - **dbt `core/`**: conformed dimensions `dim_date`, `dim_geo_br`; and the SCD
    Type 2 view `dim_code_industrialization_scd2` (gated by `--vars 'enable_curation: true'`).
  - **Dynamic curation (SCD2)**: append-only log
    `research_inputs.code_industrialization_log` (author captured from the IAP
    header `X-Goog-Authenticated-User-Email`); the UI does a live LEFT JOIN of the
    static mart to the classification dimension.
  - **Python BFF** (`src/embrapa_commodities/serving/`, optional `serving` extra):
    `sql` (@param + anti-injection allowlist), `gateway` (`@cache.memoize`), `cache`
    (flask-caching — `SimpleCache` scales multi-instance for free; `RedisCache`
    optional), `iap`, `curation` (append-only INSERT + cache invalidation).
  - **Multi-instance scaling without Redis (for free).** The dashboard scales to
    3–5+ Cloud Run instances without Memorystore: marts converge on
    `CACHE_DEFAULT_TIMEOUT` (overnight data) and the curation classification read
    uses a **short TTL** (`CACHE_CLASSIFICATION_TIMEOUT`, default 30s) that bounds
    the staleness between instances (eventual consistency ≤30s) — the instance that
    edits invalidates immediately. `RedisCache` becomes **optional** (only for
    instant cross-instance consistency under high traffic).
  - **Automated ingestion**: `embrapa ingest all` packaged as a **Cloud Run
    Job** (`deploy/ingestion/`: Dockerfile, cloudbuild.yaml, deploy.sh, schedule.sh)
    + **Cloud Scheduler** overnight (off-peak). Shortcuts `make ingest-job-deploy` /
    `make ingest-job-schedule`.
  - **Reverts the previous "never pre-aggregate" stance**: Gold remains the
    comprehensive per-source table (ad-hoc aggregation at query time), but `serving/`
    materializes pre-aggregated marts for Pushdown — they derive from Gold, they do
    not replace it.
- **New source: UN Comtrade (global bilateral trade) — `gold_comtrade_flows`.**
  A global complement to COMEX (Brazil): worldwide `reporter→partner` flows for
  HS **0801** (nuts) + **chapter 44** (wood/charcoal), ingested at the
  **HS6** level (scope expanded to the 156 six-digit leaves), across the **four
  primary regimes** X/M/RX/RM, all reporters × all partners, annual grain.
  - **Ingestion** (`embrapa ingest comtrade [--full] [--from-raw]`): a *keyed*
    JSON API (`COMTRADE_API_KEY`, free), with the key **only** in the
    `Ocp-Apim-Subscription-Key` header (never in the URL/log). Two-phase raw zone,
    *chunked* by `(year, batch of 8 reporters)` and **resumable**. **Adaptive
    split** against truncation (`fetch_chunk_adaptive`): when a call hits the
    100k-row cap (a single dense reporter already overflows it), it recursively
    splits reporters→flows→cmd and concatenates. It stays **outside
    `embrapa ingest all`** (key/quota-gated).
  - **dbt**: `silver_comtrade_flows` (keeps only the fully aggregated record —
    `motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0` — and HS6 only; drops
    the World partner `0`; normalizes `flowCode` X/M/RX/RM →
    `export`/`import`/`re-export`/`re-import`) and `gold_comtrade_flows` (the 4
    monetary conventions over `primaryValue` US$, **annual** deflation; bilateral
    reporter+partner geography via M49). Reuses `silver_currency` (USD/EUR/CNY) and
    `unit_family_conversions` (families).
  - **Seeds** of authoritative reference: `comtrade_country` (M49 → ISO3/name,
    `partnerAreas.json`), `comtrade_unit` (qtyUnitCode → family — 5=items, 8=kg,
    12=m³) and `comtrade_hs` (0801 + ch. 44, `HS.json`). Script
    `scripts/refresh_comtrade_country_seed.py`.
  - Initial historical window limited to **2022-2023** (config `COMTRADE_START_YEAR`/
    `COMTRADE_END_YEAR`) for development; extend later to older history.
- **Transport-modal dimension in COMEX (`via`).** `gold_comex_flows` gains
  `transport_route_code` (in the grain) + `via_name` via the new `comex_via` seed
  (MDIC CO_VIA codes → PT labels: Marítima, Aérea, Rodoviária…).
- **Cross-source product crosswalk** — seed `commodity_crosswalk` (links by
  *prefix*, at the commodity-concept level) + model `gold_commodity_crosswalk`
  (resolves to an exact `(source, code) → commodity`). Links the same commodity
  across PEVS (extractive code) / COMEX (NCM8) / COMTRADE (HS6) — the basis for the
  cross analyses (export coefficient, market share, trade mirror).
- **Data contract document** `docs/frontend_data_contract.md` — a Gold →
  frontend-snapshot map (field, magnitude, unit) for the BFF handoff.
- **Per-source provenance metadata** — view `gold_source_metadata` (one row per
  source: table, cadence, year coverage, counters `total_rows`/
  `products_total`/`ufs_total`, `last_refresh`), derived from the Gold tables. It
  feeds the frontend `dataStore.meta(id)` seam (provenance comes from the backend,
  not from literals); `implStatus`/`visible` stay as runtime config, documented in
  the contract.

### Changed
- **Quantities by physical unit family (schema break, no backward
  compatibility).** The fixed `[kg, t, m³, L]` format was removed. Every quantity
  row in Gold now exposes `family` (`massa`|`volume`|`energia`|
  `contagem`|`area`|`desconhecida`), `unit_native` (source label), `qty_native`
  (native value), `qty_base` (converted to the family's base unit) and
  `base_unit` (`t`/`m³`/`MWh`/`un`/`ha`). The conversion happens in **Silver**
  (Gold already delivers the final format). **`gold_pevs_production`** swaps
  `quantity_tons`/`quantity_m3` for these columns; **`gold_comex_flows`** swaps
  `stat_unit`/`stat_unit_symbol`/`statistical_quantity` for
  `unit_native`/`unit_native_symbol`/`qty_native`+`qty_base`+`family`+`base_unit`
  (statistical-unit resolution moved from Gold to Silver;
  `net_weight_kg` remains as a parallel mass-kg). **Rule:** never sum
  `qty_base` across families — every aggregation requires `GROUP BY family` (build
  `q_by_family = {massa:Σt, volume:Σm³, …}` at query time). Monetary value
  remains family-agnostic and summable.
  - New versioned seeds: **`unit_family_conversions`** (unit →
    family + `to_base`, single source — no factor hardcoded in queries) and
    **`product_unit_factors`** (a product→factor crosswalk for commodity units
    like saca/@/bushel/barril, which overrides the generic seed; no row → null
    `qty_base`, flagged for curation — never an invented conversion).
  - `data_quality_flag` reassigned to `(qty, val_brl)`. New curation (warn) test
    `assert_unconvertible_quantities_for_curation` and a
    **dbt unit test** with one case per family + a crosswalk override.
  - ⚠️ **Operational:** `silver_ibge_pevs` is incremental — run
    `dbt build --select silver_ibge_pevs+ --full-refresh` (dev **and** prod) when
    applying this change, otherwise the old partitions are left with the new
    columns null.

### Fixed
- **COMTRADE: resume now identifies the reporter batch by content, not by
  positional index.** The raw object was named `<ano>_r<índice>`, where the index
  came from slicing `list_reporters()` in the order of the UN reference JSON — if
  the UN reordered/changed the reporter set between runs, the same index would map
  to different reporters and resume silently skipped a batch whose composition had
  changed, leaving data never ingested. Now the reporters are **sorted** before
  batching and the basename is a **stable hash** of the batch's codes
  (`<ano>_r<hash>`), with `reporter_codes` recorded in the provenance.
  **Operation:** the first run after this change re-fetches the past years once
  (old basenames become orphaned; Silver dedupes).
- **COMEX/COMTRADE: the delta skip could leave a `(flow,year)`/batch
  permanently missing from Bronze.** When the raw was current, Phase 2 was skipped
  assuming "raw present ⇒ Bronze loaded" — false if a previous run archived the raw
  and aborted before the load. Now a `bronze_loaded_at` marker in the raw object's
  metadata (written after Phase 2; cleared automatically on a re-extract) is the
  source of truth: the skip happens only when the raw is current **and** has
  already been loaded.
- **BCB: the raw basename/provenance reflect the window actually archived.**
  In delta mode each series fetches only its recent overlap window, but the raw
  object was labeled with the configured `bcb_start_year` (e.g. "1980-2026") — a
  window the object does not contain. Now the label derives from the actual range
  of years in the data (`min`/`max` of `reference_date_str`).
- **`pyproject.toml`: license corrected from `MIT` to `Apache-2.0`** (the
  `LICENSE` file and all the other docs were already Apache 2.0); description
  updated to include COMEX/COMTRADE.
- **COMTRADE: ~2.5× double-counting in the Gold values/quantities.** The keyed API
  returns, per `(reporter, partner, cmd, flow)`, a **fully aggregated** record
  (`motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0`) **plus** breakdown
  rows by transport mode / customs / 2nd partner — whose value **sums into the
  aggregate**. Silver kept everything and Gold summed it all together. Fixed by
  keeping only the aggregated record in `silver_comtrade_flows` (lossless: 546,812
  groups = 546,812 rows; Bronze untouched, no re-ingest). Total COMTRADE
  US$1,779bn → US$692bn; the COMEX↔COMTRADE mirror now matches.
- **COMTRADE: wrong physical unit families.** The `comtrade_unit` seed used a
  legacy qtyUnitCode table that does not match the API's codes. Validated against
  the HS6 `standardUnitAbbr`: **5=number of items (count)**, **8=kg
  (mass)**, **12=m³ (volume)** — previously ~24% of rows fell into the wrong family.
- **BCB FX series corrected (affected PEVS and COMEX).** The configured series
  were wrong: `3694` (USD) is **annual** — insufficient for COMEX's monthly
  deflation (it only filled Januaries); `4393` (EUR) returned ~127 and `20542`
  (CNY) ~4 million — **these are not BRL/unit quotes**. Swapped for PTAX **daily
  sell**: `1`=USD, `21619`=EUR (Gold averages by year/month). **CNY was removed** —
  the BCB does not publish BRL/CNY (nor USD/CNY) in the SGS or PTAX; a yuan column
  would require an external source (follow-up). This fixes
  `val_yearfx_{brl,usd,eur}` and `val_real_*_{brl,usd,eur}` in
  `gold_pevs_production` **and** `gold_comex_flows`.
- **`bcb/client`: SGS HTTP 404 treated as a window with no data**, not an error —
  series have different start dates (USD 1984, EUR 1999), so the `--full`
  year-chunking queries windows that predate some series. Previously, a `--full`
  from `BCB_START_YEAR` broke with a 404 on the first empty window.

### Added
- **COMEX reference dimensions — readable labels on `gold_comex_flows`.**
  Three seeds from the MDIC auxiliary tables (`bd/tabelas/`): `comex_unit`
  (`NCM_UNIDADE.csv` → statistical unit, e.g. `16`=METRO CUBICO, `10`=
  QUILOGRAMA LIQUIDO), `comex_country` (`PAIS.csv` → ISO-3 + PT name) and
  `comex_ncm` (`NCM.csv`, filtered for nuts `0801*` + ch. 44 → PT description).
  `gold_comex_flows` gains readable columns via `ref()`: `ncm_description`,
  `country_name`/`country_iso_a3`, `stat_unit`/`stat_unit_symbol` — 100%
  coverage of the current data. Clarifies the quantity semantics: `net_weight_kg`
  is always kg (comparable across products); `statistical_quantity` is in the NCM
  unit (m³ for most wood, kg for nuts) — do not sum across different units.

### Changed
- **Two-phase ingestion with a `raw/` zone — standardized across ALL sources.**
  Every source now follows **extract→raw→bronze**: Phase 1 archives the extract
  *verbatim* in GCS (`raw/<source>/<dataset>/<basename>.parquet`, with provenance
  metadata — URL, ETag/Last-Modified, `fetched_at`, `rows`); Phase 2 reads the
  raw back, filters/shapes it and loads Bronze. Re-filtering, changing
  products/rules or re-deriving Bronze **does not hit the source again** — only a
  real data revision triggers a re-fetch. New primitive `core/raw.py`
  (`land_raw`/`land_raw_file`/`read_raw`/`download_raw`/`list_raw`/`raw_provenance`)
  + `GCS_RAW_PREFIX`.
  - **COMEX:** Phase 1 downloads the full CSV→Parquet (all NCMs) and re-downloads
    **only when the ETag changed** (catching revisions to any year, not just the
    current one); Phase 2 filters the raw via `iter_batches`. `--from-raw`
    re-filters with no internet.
  - **IBGE:** Phase 1 archives the SIDRA response; Phase 2 loads Bronze.
  - **BCB:** each delta window becomes a raw object stamped per run (an
    append-only trail); `--from-raw` rebuilds Bronze by re-reading the trail.
  - Every `embrapa ingest <source>` gains `--from-raw`. The dead primitive
    `core/bronze.land_and_load` was removed (all sources use the new flow).
    Plan: `PLANS/raw_zone_architecture.md`. dbt/Silver/Gold unchanged.

### Added
- **COMEX source (MDIC Comex Stat) — complete Bronze→Silver→Gold pipeline.**
  A new *foreign trade* source (the first of the `flows` form —
  origin→destination), cross-referencing production × trade × FX × inflation of the
  same product. Scope: export **and** import, Brazil nut (NCM `08012100`/
  `08012200`) + the entire chapter 44 (wood/charcoal), at the month×NCM×country×UF
  grain.
  - **Bronze (`src/embrapa_commodities/comex/`):** `client.py` bulk-downloads the
    annual CSVs from Comex Stat (`EXP_<ano>.csv`/`IMP_<ano>.csv`; `;`/latin-1)
    — *stream to disk* (100+ MB files), pandas parse in chunks, column-precise
    filter on `CO_NCM`/`CO_NCM[:2]`. EXP (11 cols) and IMP (13 cols: +
    `VL_FRETE`/`VL_SEGURO`) unified into a schema-union (export writes NULL in the
    two). It does **NOT** use the JSON API (which returned the aggregated Brazil
    total under a malformed filter, HTTP 200). `pipeline.py` has its own `run()`
    with delta by `(flow, year)` (re-fetches the current year, skips years already
    in Bronze). The command `embrapa ingest comex` is multi-chunk (events per
    `(flow, year)` in the monitor); registered in `cli.INGESTS`,
    `doctor.SOURCE_CHECKS` (`_check_comex`) and `doctor.BRONZE_TARGETS`. Config
    `COMEX_*` in `config.py`/`.env.example`.
  - **TLS:** the host `balanca.economia.gov.br` omits the intermediate CA from the
    handshake (`requests`/certifi fails; curl passes via AIA). The public
    intermediate (Sectigo R36) is vendored in `comex/_ca.py` and appended to the
    certifi bundle at runtime — **without disabling verification**.
  - **Silver/Gold (dbt):** `silver_comex_flows` (dedup at the full source grain);
    `gold_comex_flows` (ONE comprehensive `flows` table, grain
    flow×month×NCM×country×UF, aggregation via `GROUP BY` in queries). Applies the
    4 monetary conventions over `VL_FOB` (US$): `val_yearfx_*` at the month FX and
    `val_real_{ipca,igpm,igpdi}_*` (US$→BRL at the month FX → BCB index → today).
  - Coverage: `tests/test_comex_client.py` + `tests/test_comex_pipeline.py`;
    schema tests in `_silver.yml`/`_gold.yml`. Plan in
    `PLANS/comex_flows.md`.
- **Shared Bronze landing primitive (D4).** The identical tail of the Bronze
  pipelines (`ensure_bucket` → Parquet upload → `load_dataframe` with
  partition/cluster keys) was extracted into a source-agnostic primitive,
  analogous to D1 (`core/http.py`): each `run()` keeps only what is specific to the
  source. `ensure_dataset` is left out because the BCB needs the dataset *before*
  the extract (delta lookup). **Note:** this step evolved, still within this
  cycle, into the two-phase ingestion with a `raw/` zone — the final primitive is
  `core/raw.py` (see "Changed" above), not an intermediate
  `core/bronze.land_and_load` (introduced and removed within this same cycle).
  Observable behavior preserved; coverage in `tests/test_core_raw.py`.
- **`core/http.py` — shared HTTP primitives (D1).** A new factory
  `http_retry_policy(transient_exc, deadline_s, max_attempts=5, before_sleep=None)`
  and helper `get_drained(url, *, total_deadline_s, transient_exc, context, ...)`
  encapsulate the tenacity retry policy and the manual body drain under a
  wall-clock deadline (slow-byte defense) that were previously duplicated in the
  IBGE and BCB clients. Shared constants: `DEFAULT_TIMEOUT`, `DEFAULT_HEADERS`,
  `RETRYABLE_STATUS_CODES`. Observable behavior preserved byte for byte —
  source-specific deadlines (75s/180s in IBGE, 60s/120s in BCB) remain in the
  clients; unique defensive logic (IBGE period-halving, BCB year-chunking) also
  did not migrate. Coverage: 11 new tests in
  `tests/test_core_http.py` (including the slow-byte deadline test migrated from
  `test_ibge_client.py`) + 2 "delegate" tests asserting the kwargs passed to
  `get_drained` in each client.
- **Retry observability in the BCB client (D1.1).** `_fetch_window` now wires a
  `before_sleep=_emit_retry` hook into the tenacity policy, symmetric to IBGE —
  SGS series retries now emit a `retry` event
  (`series`, `window`, `attempt`, `reason`) that shows up in `embrapa monitor`.
  Unlike IBGE (which uses a contextvar because the UF lives one frame up), the
  `(code, window)` context comes directly from `retry_state.args`, since
  `_fetch_window` is itself the retried function. Coverage: a test of the hook's
  logic + a regression guard on the wiring (`before_sleep`).

### Changed
- **BCB inflation/currency pipelines collapsed into `bcb/series.py`.** The two
  pipelines were ~90% identical (`_extract`, `_effective_start_year`, `run`);
  they now share a generic SGS series pipeline parameterized by a
  `BcbSeriesSpec` (`kind`, `label_column`, `series_map`, `table`, `schema`, and the
  only genuinely source-specific line — `overlap_start_year(last) -> int`).
  `bcb/inflation.py` and `bcb/currency.py` became thin shims defining their spec
  and delegating. Public entry points (`inflation.run`/`currency.run`),
  constants (`DELTA_OVERLAP_MONTHS`, `BRONZE_SCHEMA`) and observable behavior
  preserved. **Deliberately reverts** the old note in
  `docs/adding_a_data_source.md` ("do not extract `_effective_start_year`"):
  on closer inspection, the difference was one line, today a `Callable` knob. The
  doc was updated to steer SGS series toward the spec, and differently-shaped
  sources toward writing their own `run()`. Tests consolidated: the duplication
  of the two test files became a single `tests/test_bcb_series.py` parameterized
  over the two specs + two thin per-variant files (the spec contract).
- **Gold renamed `gold_commodity_matrix` → `gold_pevs_production`**, adopting the
  `gold_<source>_<form>` convention (`production` for output measurement like PEVS;
  `flows` for origin→destination flow in future trade databases). Reinforces the
  rule of **one comprehensive Gold table per source** (ad-hoc aggregation at
  query time; pre-aggregated marts live in the `serving/` layer — see the
  Pushdown Computing item above).
  **External action required:** repoint the Looker Studio source to
  `gold.gold_pevs_production` and drop the orphaned `gold.gold_commodity_matrix`
  table in prod after the next `make dbt-build-prod` (see `docs/migration_history.md`).

### Fixed
<!-- Bug fixes -->

### Removed
- **Dash + Plotly UI layer removed (2026-05-29).** The frontend is being
  rebuilt with the Claude Design System in a separate flow. The following were
  deleted: the `src/embrapa_commodities/dashboard/` package, the
  `tests/test_dashboard_*` tests, the scripts `scripts/dashboard_*` /
  `scripts/check_dashboard_size.py` / `scripts/dashboard-*.ps1`, the
  `Dockerfile`, the workflow `.github/workflows/dashboard-smoke.yml`, the
  `docs/auth.md` and the Claude Code skills `run-dashboard`,
  `dash-page-scaffold`, `new-chart-component`, `deploy-cloud-run`. The `dashboard`
  and `visual` extras in `pyproject.toml`, the `check-dashboard-size` hook
  in `.pre-commit-config.yaml`, the `--extra dashboard` in `ci.yml` and the
  `dashboard-*` / `test-smoke` targets in the `Makefile` were also removed.
  The backend (Medallion pipeline + dbt + `embrapa` CLI) remains 100%
  functional. The next handoff will join the new design system with
  this backend.

---

## [0.1.0] — 2026-05-26

> Initial release — functional end-to-end Medallion pipeline.

### Added

- **IBGE PEVS ingestion pipeline** via the SIDRA API with support for multiple products and periods.
- **BCB ingestion pipeline** (IPCA/IGP-M/IGP-DI inflation + USD/EUR/CNY FX) via the SGS API.
- **Delta ingestion** for the BCB — only new data is fetched by default.
- **Chunked ingestion** (`ibge-batch --chunk-years`) for large historical windows.
- **Silver layer (dbt)**: typing, dedup, IPCA chain index.
- **Seed `historical_currency_factors`**: absorbs Brazilian currency reforms (1942–1994).
- **Gold layer (dbt)**: `gold_commodity_matrix` table with 22 denormalized columns.
- **Aggregated Gold tables**: `gold_commodity_state_year`, `gold_commodity_year_product`.
- **Unified CLI** with Typer: `embrapa ingest|discover|dbt|doctor|backup-gold`.
- **Web dashboard** with Dash + Plotly (multi-page), deployed via Cloud Run.
- **Multi-stage Dockerfile** with a slim, non-root image, Gunicorn.
- **Service Account Impersonation** (OAuth 2.0) — no distributed keyfiles.
- **Four Service Accounts** with separation of responsibilities (reader, pipeline, dashboard, AI).
- **Gold backup → GCS** (`embrapa backup-gold`, `make dbt-build-prod-with-backup`).
- **`embrapa doctor`**: environment health diagnostics.
- **dev/prod separation** in the dbt schemas with auto-expiration of dev tables (7 days).
- **CI/CD**: GitHub Actions with lint (Ruff), test (pytest), dbt parse.
- **Pre-commit hooks**: gitleaks, ruff, file-hygiene, dashboard size ceiling (500 LOC).
- **Smoke test** of the dashboard with real BQ.
- **Visual check** with Playwright (headless screenshots → `artifacts/`).
- **Cross-platform automated setup**: `setup.sh`, `setup.bat`, `setup.ps1`.
- **Complete documentation**: setup, IAM, auth, cost safety, ownership transfer, testing.

---

<!-- Template for new versions:

## [X.Y.Z] — YYYY-MM-DD

### Added
### Changed
### Fixed
### Removed
### Security
### Deprecated

-->
