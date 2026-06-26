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

**Detector (REVISED — VALIDATED on live BigQuery, 2026-06-26).** The magnitude-only fence the first
workflow proposed CANNOT split outlier from problemático (both are "high") — proven false-positives on
legit Amazon timber. The working method is an **implied-price (unit-value) consistency test**: a typo
breaks `value ÷ quantity` (scale-invariant), a legit giant does not. Confirmed on real data:
- COMEX: within a product the VALUE tail is 26.5× the median but the PRICE tail is 10.5× (P99); the
  extreme price tail is unambiguous typos (charcoal $1,440/**1 kg**; rice $13,800/**1 kg**; soybean meal
  $3 for 2,500 t) — all `weight=1` placeholders / dropped digits, NONE legit giants.
- The **deflation requirement is load-bearing**: IBGE price MUST use `val_real_ipca_brl` — nominal
  `val_yearfx_brl` manufactured a fake 20% near-zero-price tail (66,826 rows, ALL pre-1995 hyperinflation).
  With deflation, PEVS >100× rate = **0.003%**.

Rule, per group (IBGE `(product_code, family, unit_native)`; trade `(flow, code)`), sample gate `n>=MIN_OBS`:
- `price = real_value / quantity` — IBGE `val_real_ipca_brl/qty_native`; trade `val_yearfx_usd/net_weight_kg`
  (USD, post-1989, no BR-inflation issue). Compute `ln_med = median(LN(price))` per group (APPROX_QUANTILES).
- `price_dev = LN(price) - ln_med`.
- **PROBLEMATIC** iff `ABS(price_dev) >= LN(k_price)` — the implied price is economically absurd → a value
  or quantity typo. Attribute: `price_dev > 0` (value-too-high or qty-too-low) → if the value is the high
  outlier `PROBLEMATIC_VALUE` else `PROBLEMATIC_QUANTITY`; `price_dev < 0` → the opposite. (Both QUANTITY
  ids also cover trade `net_weight_kg`.) Needs a small magnitude floor to skip trivia.
- **OUTLIER_{QUANTITY,VALUE}** iff the measure is in the product's high tail (one-sided log fence,
  `(LN(measure)-p50)/(p75-p50) >= k_outlier`, `n>=MIN_OBS`, `p75>p50`) AND the row is NOT problemático
  (price consistent) → "bem acima do esperado mas válido."
- Precedence (donut partition): MISSING_*/INCOMPLETE > PROBLEMATIC_VALUE > PROBLEMATIC_QUANTITY >
  OUTLIER_VALUE > OUTLIER_QUANTITY > OK.

**dbt var defaults:** `enable_quality_outliers=false`, **`quality_price_k=100`** (price >100× or <1/100× the
product median = typo; validated rates: COMEX 0.19%, PEVS 0.003% at 100×), `quality_outlier_k=4.0`
(magnitude fence for the OUTLIER tier), `quality_min_obs=100`, magnitude floor (skip trivia) massa 100 t /
volume 100 m³ / contagem 1000 head / value 10000 (real BRL or USD). PPM `measure_kind='stock'` (herd) has
NO value → quantity OUTLIER only, never a price/value flag.

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
