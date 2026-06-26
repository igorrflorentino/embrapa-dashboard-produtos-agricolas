# PLANS — Q1 Outlier/Problemático quality flags + F7 Ciclo-de-Vida visibility gate

> Status: **F7 IMPLEMENTED; Q1 wiring in progress (detection ships OFF by default).**
> Designed data-grounded (adversarial workflow validated on live BigQuery, 2026-06-26).
> Origin: the "Contrato de Dados" sheet verification (`docs/audits/curadoria_pr_audit_2026-06-26.md`
> is the catalog audit; this doc is the spreadsheet-vs-code integration follow-up).

## The decisive data finding (why Q1 detection ships OFF)

Every **global** statistical fence tested on live Gold false-accuses legitimate records:
- PEVS quantity max log-z = **4.51** (z>6 unreachable); robust log-Tukey k>4 flags **722** rows,
  all legitimate recurring Amazon timber (Paragominas/Carauari 1989–1996).
- COMEX value z>6 = **2 rows**, both ~US$281k banana→Uruguay (trivial, not typos), while
  billion-dollar rows clear. Within-series ratio over-flags (4.8% at ≥10×); ≥1000× spikes are real
  regime shifts.

**Conclusion:** there is no global threshold separating "typo" from "legitimate giant" on this data.
→ The taxonomy + detection wiring ships fully (tested, fail-closed), but the detector is gated behind
`var('enable_quality_outliers', false)`. When OFF (default = today) the gold models compile
**byte-identical** to the current 4-value flag. Enabled **per source** only after an operator validates
the flagged rates on a live build. This is "build outlier detection" without shipping false accusations.

## FEATURE A — F7 visibility gate (DONE)

`ciclo_de_vida = 'Fazer Ingestão mas deixar indisponível'` hides a commodity everywhere a researcher
sees it, but NEVER from the Curadoria admin editor / orphan / crosswalk. Today: 46 active prefixes, all
visible → the gate is a **data no-op** until a researcher hides something.

**Single source of truth:** `dbt/models/core/dim_commodity_visibility.sql` (view) emits only HIDDEN
`(source, code_prefix)` rows (latest-wins, active, indisponível). Gate predicate = `NOT EXISTS … LIKE
code_prefix||'%'` over it. A code with no row stays visible (handles PPM=0, partial coverage).
`dim_commodity_catalog` is untouched (admin/crosswalk still see hidden-but-active rows).

Files: `dim_commodity_visibility.sql` (new), `macros/hidden_code_predicate.sql` (new); predicate added to
serving marts (pevs/pam/ppm/comex+seasonality/comtrade annual) + `serving_quality_by_source.sql`;
`serving/sql.py` `visibility_clause()` for direct-Gold readers (quality_timeseries, quality_by_product,
production_by_municipio_yearly, Dados raw on `gold_*` facts); `seam_base._crosswalk_df()` anti-joins it.
Admin readers (`fetch_commodity_catalog`, orphan, lifecycle, crosswalk) are EXEMPT by design.

Tests: dbt singular `assert_no_hidden_code_in_marts.sql` (0 rows) + a `dim_commodity_visibility`
unit_test (disponível/indisponível/tombstone fixture, latest-wins); pytest gate tests + admin-exemption
regression + `visibility_clause` string test; no vitest (rows-only change).

## FEATURE B — Q1 outlier/problemático (wiring lands; detection OFF by default)

**9-value enum:** `OK, MISSING_VALUE, MISSING_QUANTITY, MISSING_WEIGHT, INCOMPLETE, OUTLIER_QUANTITY,
PROBLEMATIC_QUANTITY, OUTLIER_VALUE, PROBLEMATIC_VALUE`. COMEX/COMTRADE weight reuses the QUANTITY ids.

**Precedence (donut stays a partition):** MISSING_*/INCOMPLETE > PROBLEMATIC_VALUE > PROBLEMATIC_QUANTITY
> OUTLIER_VALUE > OUTLIER_QUANTITY > OK.

**Detector** = per-source robust one-sided **log-Tukey fence** + sample gate + magnitude floor +
recurrence guard on PROBLEMATIC:
- group: IBGE `(product_code, family)`; COMEX value `(flow, ncm_code)`, weight `(flow)`; COMTRADE
  `(flow, cmd_code)`. Value fence on **deflated** `val_real_ipca_brl` (IBGE) / source **USD** (trade) —
  never nominal.
- over `LN(x)` for x>0: `p50,p75` via `APPROX_QUANTILES(...,1000)`; `excess=(LN(x)-p50)/(p75-p50)`.
- OUTLIER iff `n>=MIN_OBS and (p75-p50)>0 and excess>=k_outlier`.
- PROBLEMATIC iff outlier AND `excess>=k_problematic` AND `x>=magnitude_floor(family)` AND
  `COUNT(DISTINCT year) at that magnitude < recur_min` (the recurrence guard kills the multi-year-timber /
  bulk-cargo false positives).

**dbt var defaults:** `enable_quality_outliers=false`, `quality_outlier_k=4.0`,
`quality_problematic_k=6.0`, `quality_min_obs=30`, `quality_recur_min_years=3`; magnitude floors massa
1000 t / volume 1000 m³ / contagem 10000 head / USD-or-value 100000. Validated rates ON: PROBLEMATIC
≤~0.07% (COMEX), 0% on IBGE; OUTLIER ≤~0.19%.

**Files:** `dbt_project.yml` (vars); `macros/data_quality_flag.sql` (extend signature, 2-arg back-compat,
precedence); `macros/quality_outlier_ctes.sql` (new — bounds CTE + `quality_level_expr` compile-gated by
the var → null when off); the 5 gold models (bounds CTEs + level exprs; PPM stock skips value; COMEX
migrates inline CASE keeping MISSING_WEIGHT); `_gold.yml` accepted_values += 4 ids + new unit_tests +
singular `assert_quality_flag_in_enum.sql`; `serializers.py` `_FLAG_KEY`/`_FLAG_LABEL_PT` += 4 pt-BR;
`data.js` QUALITY_FLAGS += 4; `ViewQuality.jsx` QTS_KEY += 4; `contracts.js` qualityTs keys; `glossary.js`
prose. pt-BR labels: "Quantidade/Valor atípica(o) (válida/o)" + "… problemática(o) (provável erro)".

## Operator runbook (prod, after merge)

1. `make dbt-build-prod-with-backup` (rewrites `data_quality_flag` on every gold fact — backup-first).
2. F7 check: `SELECT * FROM gold.dim_commodity_visibility` → expect **0 rows today** (no-op confirmed).
3. Q1 inert check (flag still OFF): `SELECT source, data_quality_flag, COUNT(*) FROM
   serving_quality_by_source GROUP BY 1,2` → only the original 4-value set appears.
4. Q1 per-source enable (one source at a time): rebuild with `--vars 'enable_quality_outliers: true'`,
   inspect `SELECT data_quality_flag, COUNT(*)`, spot-check flagged rows are NOT the largest legit
   producer. Only then promote. **Do not auto-enable globally.**

## Sandbox vs operator

Sandbox-verifiable: `dbt parse`/`compile` (PYTHONUTF8=1), dev-target unit_tests, pytest, vitest,
ruff/sqlfluff; **offline-compile the gold models with the flag OFF and diff `data_quality_flag` against
`main` to prove byte-identical**. Operator-only (no `*.googleapis.com` in sandbox): every prod
`dbt build`/`test`, the F7 no-op confirmation + live hide/restore smoke test, all
`enable_quality_outliers: true` validation/enable builds.
