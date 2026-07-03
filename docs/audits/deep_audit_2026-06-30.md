# Deep audit — 2026-06-30

> **Status (2026-06-30): all 21 confirmed findings FIXED** in branch
> `claude/agitated-goldberg-947a4d`. Backend 1199 pytest + ruff clean; frontend
> 723 vitest + eslint clean (coverage thresholds met); dbt models compile
> (`dbt parse`) + sqlfluff clean. M2 was resolved as the chip/data consistency
> fix (the empty-facet = "no constraint" data semantics are intentional/documented).
> L3/L4/L7 were resolved by documenting the accepted behavior (see each entry).

Multi-agent bug/inconsistency audit of the Embrapa Commodities Dashboard
(backend Python + dbt + React frontend). Every candidate finding was
**adversarially verified** — independent reviewers re-read the cited code and
tried to *refute* the claim (default = not-a-bug); only findings a reviewer
could reproduce from the real code survived.

## Method & scope

- **17 finder dimensions** in parallel: serving SQL/injection, serving gateway &
  cache, webapi routes/validation, serializers↔`contracts.js` parity,
  registries/pt-BR formatting, IBGE ingestion, BCB ingestion, COMEX/COMTRADE
  ingestion, curation & catalog lifecycle, dbt deflation/quality/1985/visibility
  macros, dbt silver/gold grain & incremental, dbt serving marts & seeds,
  frontend data layer (ragged-series focus), frontend chart math, frontend
  filters/gating/URL-state, frontend views, config/CLI/doctor,
  security/CI/deploy, language-rule & doc/contract drift.
- **Verification**: 2 independent adversarial reviewers per claimed
  *critical/high* finding, 1 per *medium/low*.
- **Mechanical checks (all green)**: `ruff check` + `ruff format` clean (115
  files); `eslint` (`src/data src/charts src/ui`) clean — **0** lint/format
  issues. The bugs below are logic/data-level (not linter-catchable).

**Result**: 36 raw findings → **21 confirmed**, 15 refuted. No critical, no
confirmed high. Top tier is **1 data-integrity (medium)** + **2 medium UX/URL** +
**18 low** (latent / cosmetic / consistency).

---

## Tier 1 — worth fixing (medium)

### M1 · Orphan purge keys off `codigo_commodity`, but detection keys off `code_prefix`
- **File**: `src/embrapa_dashboard/serving/catalog_lifecycle.py:286` (`purge_plan`); cf. `serving/gateway.py:817` (detection), `serving/curation.py:349-352` (tombstone).
- **Category**: data-integrity · **Verifiers**: 2/2 confirmed (one rated high, one medium).
- **Mechanism**: `purge_plan(banco, code)` emits `DELETE … WHERE {col} LIKE '{code}%'`, where `code` is the operator-supplied `codigo_commodity` (the worklist identity, and what the status guard at `:280` forces). Orphan **detection** instead matches Gold via `g.code LIKE t.code_prefix || '%'`, and `remove_commodity_catalog` deliberately tombstones with the entry's *real* `code_prefix` (with a comment explaining why). `purge_plan` never reads `code_prefix`.
- **Trigger / impact**: the catalog explicitly supports a coarse prefix (`code_prefix='12'`, `codigo_commodity='1203'`). Detection flags the orphan via `LIKE '12%'`; the generated purge is `LIKE '1203%'` → **under-purges** (leaves `1201`/`1204`/… behind — the very rows that made it an orphan survive a "completed" purge), and `mark_purged` then writes a **false "purged" audit record**. The reverse (codigo broader than prefix) would over-delete. Tests only ever exercise `code == prefix`, so the divergence is uncovered.
- **Mitigations already present**: operator-gated, backup-first, prints DELETEs for a human to run by hand; only fires for the non-default coarse-prefix configuration.
- **Fix**: have `purge_plan` resolve the tombstone's actual `code_prefix` (already returned by `fetch_orphan_commodities` / available on the worklist row) and build the DELETE with `LIKE code_prefix||'%'`, mirroring detection. Keep the `[A-Za-z0-9.\-]+` sanitization; refuse to plan if the prefix can't be resolved.

### M2 · Empty geo facet (`[]`) is treated as "no constraint" — diverges from `basket`/`states` and can contradict the filter chip
- **File**: `frontend/src/ui/dataFilters.js:191` + `:67-73`; chip `frontend/src/ui/filterSummary.js:70-71`.
- **Category**: correctness / UX-consistency · **Verifiers**: 2/2 confirmed (high/medium). **Auditor note: downgraded to medium** — see below.
- **Mechanism**: `geoFacetSets` marks a facet constrained only when `size > 0` (`:70`), and `_hasGeoKeys` requires `summary[k].length` truthy (`:191`). So `munis: []` ⇒ mesh not fetched ⇒ `subUfActive=false` ⇒ `geoSource = ufYearlyAll` (all-UF grid).
- **The nuance** (why not high): this is **documented, deliberate design** — `dataFilters.js:41-44` / `:187-190` state `[]` = "no constraint", specifically so a *cascade-emptied child* (selecting a parent after "Limpar" leaves children empty) doesn't collapse the view to nothing. The real defect is twofold: (a) **inconsistency** — `basket:[]` and `states:[]` mean "none" (zero rows), but geo `[]` means "all"; (b) a user can clear the **município column directly** via "Limpar" → persistent `[]` the cascade never refills, while the chip can read `"… · 0 municípios"` even though every município is shown. Reachable via shared URL too (the `mn=-` sentinel round-trips `[]`).
- **Fix options**: distinguish a cascade-emptied `[]` from a user-cleared `[]` (e.g. only the cleared column resolves to zero cities), **or** at minimum make the chip say "todos" whenever the facet is unconstrained so the label can't contradict the data.

### M3 · Share/permalink URL serializes the full município code array → oversized link / HTTP 414
- **File**: `frontend/src/ui/AppShell.jsx:223` (`mn: arrParam(summary?.munis)`); cf. `FilterMenu.jsx:631`.
- **Category**: url-state · **Verifiers**: 1/1 confirmed (high).
- **Mechanism**: `munis` is omitted from the URL only when **all** ~5570 municípios are selected; any partial selection joins every 7-digit code into `mn=`. Selecting "all" municípios of a few large states (e.g. MG+SP+BA ≈ 1900 codes) makes `mn` ≈ 15 KB, exceeding the ~8 KB request-line limit of typical proxies/Cloud Run/IAP → the shared link 414s or is silently truncated (corrupting the restored selection). This re-introduces exactly the failure the `POST /api/municipio-yearly` redesign eliminated for queries — the share URL is the remaining GET path.
- **Fix**: past a length cap, omit `mn` and serialize only the higher sub-UF facets (`me/mc/it/im`) that produced the selection (or store server-side and reference by id); surface a UI note when the município selection is too large to embed.

---

## Tier 2 — low (latent / data-completeness / dbt)

| # | Finding | File:line | Note |
|---|---------|-----------|------|
| L1 | `silver_comex_flows.reference_date` uses non-SAFE `DATE(CAST(CO_MES AS INT64))`; a malformed/out-of-range `CO_MES` **raises** instead of becoming NULL, so the trailing `where reference_date is not null` can't drop it — a single bad month in a republished file crashes the nightly Silver build. Sibling models use `safe.parse_date`. | `dbt/models/silver/silver_comex_flows.sql:69` | latent build-crash |
| L2 | `silver_bcb_inflation` does **not** filter Bronze by the configured `series_codes` (currency does). A code dropped from `BCB_INFLATION_SERIES` but still referenced in the Gold pivot var would deflate new years against a frozen/stale index. | `dbt/models/silver/silver_bcb_inflation.sql:17-26` | config-drift risk |
| L3 | IGP-DI (SGS 190, history back to 1944) is truncated at `bcb_start_year=1980`, so PAM/PPM production 1974–1979 gets NULL `val_real_*` even though IGP-DI alone could deflate it. NULLs are honest (not wrong), but undocumented in-product. | `config.py:198` → `annual_deflation_ctes.sql` / `gold_*_production.sql` | data-completeness |
| L4 | COMTRADE `fetch_chunk_adaptive` treats an exactly-100k-row **complete** result as truncated (`len(df) < CAP` strict) → raises `ComtradeTruncationError` and the leaf chunk never lands in Bronze. Vanishingly unlikely in the 0801+44 scope. | `comtrade/client.py:400,436` | off-by-one |

## Tier 2 — low (backend robustness / cache)

| # | Finding | File:line | Note |
|---|---------|-----------|------|
| L5 | `flow` query param is **unvalidated** on `/snapshot`, `/geo-yearly`, `/municipio-yearly` (siblings `currency`/`correction`/`metric` 400 on bad input). A typo like `flow=Exportacao` binds verbatim, matches 0 rows → empty-but-200 (blank chart, no signal). UI only ever emits valid values, so reachable only via hand-crafted URL. | `webapi/routes.py` (`/snapshot` ~379, `/geo-yearly` ~415, `/municipio-yearly` ~467) | add `_ALLOWED_FLOWS` guard |
| L6 | `fetch_cross_series` is memoized on `uf_codes`, but for COMTRADE metrics the query drops the UF filter — so `('SP',)` and `('RJ',)` cache **identical** national results under different keys (redundant BQ round-trips + wasted SimpleCache slots vs the 500-entry cap). No correctness impact. | `serving/gateway.py:851-887` | normalize key |
| L7 | Dados raw-row inspector can briefly show a **stale pagination total** in the ~10-min window after a nightly dbt rebuild changes row count (count from a separately-memoized schema entry vs live per-offset rows). Self-heals at TTL; cosmetic. | `serving/gateway.py` (`fetch_table_count`/`fetch_table_schema`) | shorten num_rows TTL |
| L8 | `fetch_orphan_commodities` cache (30s TTL) is **not** invalidated on a catalog tombstone write (only `fetch_commodity_catalog` is), so the Descontinuados worklist lags read-after-write up to 30s. Feature is FROZEN; advisory. | `serving/curation.py:373-374,465-470` | also `delete_memoized` the orphan reader |

## Tier 2 — low (frontend display / cosmetic)

| # | Finding | File:line | Note |
|---|---------|-----------|------|
| L9 | `ViewProductivity` `fmtArea`/`fmtProd` have no sub-1000 branch → always `/1e3` with 0 decimals: `500 ha` renders as **"1 mil ha"**, `400 ha` as "0 mil ha"; the empty loading frame shows "0 mil ha"/"0 mil t". National KPI strip only. | `frontend/src/ui/ViewProductivity.jsx:30-31` | add `>=1e3` + bare-unit tiers |
| L10 | `ViewConcentration` product distribution takes each product's **last array element** as its value, but series are ragged by year — a discontinued product ends earlier, so Gini/HHI/top-3/Lorenz mix products at different terminal years while the panel is labeled `yearEnd`. (Geo side correctly uses `ufLatestYear`.) Author comment acknowledges the approximation; the asymmetric labeling is the defect. | `frontend/src/ui/ViewConcentration.jsx:62-65` | align to a fixed cross-section year, or relabel |
| L11 | `ViewValueVolume` count-family note hard-codes "efetivo dos rebanhos (cabeças) … não somáveis … veja Rebanho" gated only on `countFamily`, not on a STOCK being present — so a value-bearing basket of count **flows** (ovos/mel) shows a false herd note pointing to a Rebanho view that would be empty. `ViewOverview` discriminates via `hasStock`. | `frontend/src/ui/ViewValueVolume.jsx:149-156` | gate on `hasStock` like ViewOverview |
| L12 | `Heatmap` sets missing cells to `null` (correct, drawn as gaps) but the trace lacks `hoverongaps:false`, so a null cell still shows a hover box and `%{z:,.2f}` renders a blank value token instead of "sem dado". Cosmetic. | `frontend/src/charts/Heatmap.jsx:34-48` | `hoverongaps:false` or customdata |
| L13 | `fmtBRL` buckets on the **signed** value (`n >= 1e9`), unlike the canonical `magnitudeParts()` which uses `Math.abs`; a negative billion would render unabbreviated. **Dead code** (no live callers). | `frontend/src/ui/data.js:220-226` | bucket on `abs` and re-apply sign, or delete |

## Tier 2 — low (security hardening / language / parity)

| # | Finding | File:line | Note |
|---|---------|-----------|------|
| L14 | CSV export `esc()` quotes for delimiter safety but does **not** neutralize leading `= + - @` → spreadsheet **formula injection** via researcher-editable commodity names (Curadoria "Cadastro de commodities"). Both editor and exporter are trusted IAP users, so it's defense-in-depth, not a privilege crossing. | `frontend/src/ui/csvExport.js:18-22` | prefix `'` on `^[=+\-@\t\r]` (text columns) |
| L15 | `doctor.py` `_BACKUP_RUN_RE` hardcodes `'backups/'` instead of deriving from `BACKUP_PREFIX` (which it imports and uses elsewhere). No current fault, but changing `BACKUP_PREFIX` would make doctor falsely report "no snapshot" (exit 1) despite valid backups. | `src/embrapa_dashboard/doctor.py:487` | build regex from `BACKUP_PREFIX` |
| L16 | `purge-orphan` CLI emits **Portuguese** operator prose ("Plano de purga", "Faça um backup…", "Atenção…"). Project rule: operator/CLI messages are dev-only → English. It's the lone Portuguese-emitting command in `cli.py`. | `src/embrapa_dashboard/cli.py:969-994` | translate to English (keep DELETE SQL verbatim) |
| L17 | Backend `registries.py` View/perspective registry has drifted from the authoritative frontend `views.js`: missing the `dados` view, missing `dataBlocked` on `cross_chain`/`cross_lag`, and keeps the FROZEN `curated` group inline+live. **No runtime impact** — the View helpers have no callers (only `Banco`/`banco_by_id` are consumed); pure parity/doc drift against the file's own "keep aligned" contract. | `webapi/registries.py:445-696` and `:674-695` | re-sync, or delete the unused View block |

> L17 and the "registries missing `dados` view" finding are two views of the same `registries.py`↔`views.js` parity drift; fix together.

---

## Refuted (notable) — flagged then dismissed on closer reading

These were raised by a finder but **could not be reproduced** by the adversarial
reviewers; kept here so the reasoning is on record.

- **COMTRADE retired HS6 codes never ingested** (claimed *high*) — **refuted 2/2**. The premise ("the HS reference is current-vintage only") is false: UN Comtrade `HS.json` is consolidated across revisions, so retired leaves (`080120`, `4401xx`, `4402xx`) *are* enumerated; `config.py` even adds `080120:castanha_historica` explicitly. The succession join is live, not dead code.
- **F7 `visibility_clause` LIKE over-match on `%`/`_` in `code_prefix`** — **refuted**. The write gate (`curation.py:227-231`) rejects `%`/`_` in `code_prefix` with a dedicated test, so a wildcard can never reach `dim_commodity_visibility`. Same for the `hidden_code_predicate` macro variant.
- **Basket cap 600 > gunicorn request-line → 414 instead of 400** — **refuted** (had been *confirmed* in the first pass with a single reviewer; the second, fuller pass dismissed it). The code comment explicitly documents and *accepts* deferring oversized-request-line rejection to gunicorn; no legitimate basket approaches 400+ codes, and the cap also guards the POST path. Documented status-code nuance on an unreachable input, not the genuine `/municipio-yearly` 414 class.
- **`/feedback` surfaces English validation errors to users** — **refuted**. The textarea `maxLength` (5000) exactly equals the server limit, and empty/category are guarded client-side, so the English string is unreachable in product use.
- **`fmtRows` missing null guard** — **refuted**. Asymmetric vs siblings, but all 3 call sites guard externally; latent only.
- Also refuted (no reproducible trigger): COMTRADE 429/`Retry-After` run-stop, `quality_value_floor` USD calibration, COMEX `net_weight_kg` zero-sentinel, gold IBGE `max(qty_native)` second-unit drop, `Donut` all-zero blank ring, `ufColorScale` sub-1 domain floor.

---

## Bottom line

The codebase is **healthy**: 0 critical/high confirmed, lint/format/eslint
clean, the SQL surface is parameterized (no injection found), the F7 visibility
gate and curation write-gates hold, and the known "ragged-series-by-year" class
is largely handled (only `ViewConcentration`'s product cross-section and the
`Heatmap` hover label slip through, both cosmetic). The one finding with real
data-integrity weight is **M1** (orphan purge prefix mismatch) — operator-gated
and backup-first, but it can falsify the purge audit record. **M2/M3** are
genuine UX/URL inconsistencies. Everything else is latent, cosmetic, or
parity/doc drift.

**Suggested order**: M1 → M3 → M2 → L1 (build-crash latent) → the rest as a
cleanup sweep.
