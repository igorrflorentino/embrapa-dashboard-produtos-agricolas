---
name: code-audit
description: >-
  Perform a strategic architectural health audit of the codebase. Use when
  asked to audit code quality, check complexity, find architectural smells,
  review maintainability, get a health score, or before closing a major feature.
  Do NOT use for routine lint fixes — use lint-and-test for that.
---

# Code Audit — Embrapa Commodities

This skill produces a structured architectural report. It does **not** auto-fix anything — its job is to analyse, categorise, and propose a prioritised refactoring plan.

## Step 1 — Run all audit tools

```powershell
# Preferred: use venv scripts directly (avoids uv re-sync file-lock on Windows)
$radon  = ".venv\Scripts\radon.exe"
$ruff   = ".venv\Scripts\ruff.exe"
$pytest = ".venv\Scripts\pytest.exe"

# 1. Cyclomatic complexity (per function, ranked worst-first)
& $radon cc src/ --min B --show-complexity --average

# 2. Maintainability Index (A=excellent … F=unmaintainable, per file)
& $radon mi src/ --show --sort

# 3. Halstead metrics (effort + volume, per file)
& $radon hal src/

# 4. Complexity violations via ruff (McCabe threshold = 10)
& $ruff check src/ --select C90 --output-format concise

# 5. Test coverage
& $pytest --cov=src/embrapa_dashboard --cov-report=term-missing -q
```

> **Windows note:** If `uv run radon` fails with "Acesso negado", it means another process holds a `.dist-info` lock (VS Code, a running dashboard server). Use the `.venv\Scripts\` form above instead.

## Step 2 — Interpret the scores

### Cyclomatic Complexity (radon cc)

| Grade | Value | Meaning |
|-------|-------|---------|
| A | 1–5 | Simple, low risk |
| B | 6–10 | Moderate, acceptable |
| C | 11–15 | Complex — review |
| D | 16–20 | High risk — refactor soon |
| E/F | 21+ | Unmaintainable — refactor now |

Functions graded **C or worse** are candidates for decomposition.

### Maintainability Index (radon mi)

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 20–100 | Maintainable |
| B | 10–19 | Moderate debt |
| C | 0–9 | Hard to maintain — restructure |

Files graded **C** need immediate attention.

### Ruff C90 (McCabe)

Reports any function exceeding complexity 10. These are the same functions radon flags as C/D/E — cross-reference to confirm priority.

### Coverage (pytest-cov)

- **>80%** — healthy
- **60–80%** — acceptable for this project phase
- **<60%** — modules with zero/low coverage are high-risk for silent regressions

## Step 3 — Produce the audit report

After running the tools, structure findings into exactly three categories:

### 🔴 Critical Architecture
Functions/files where `radon cc` grade ≥ C **and** `radon mi` grade = C, or any circular import detected. These represent the highest risk of bugs and the hardest areas to extend. List each with its score and the file/function location.

### 🟡 Code Smells
Functions with `cc` grade B or C individually that are otherwise in healthy files. Includes: functions doing more than one thing (visible from high argument count + high complexity), duplicated logic across pages, or callbacks with side effects.

### 🟢 Conventions
Low-severity items: missing docstrings on public functions, inconsistent naming, or long files (>300 lines) that could be split. These are low priority and can be batched.

## Step 4 — Health summary

Present a table like this:

```
Module                        | MI  | Max CC | Coverage | Grade
------------------------------|-----|--------|----------|------
cli.py                        | A37 | C(13)  | 91%      | ✅
comtrade/pipeline.py          | A60 | C(12)  | 94%      | ✅
bcb/inflation.py              | A95 | A(4)   | 100%     | ✅
ibge/pipeline.py              | A66 | B(6)   | 96%      | ✅
```

Focus coverage on the ingestion/transform backend under
`src/embrapa_dashboard/` — today `{cli, config, doctor, backup, observability,
discover}` plus the `{ibge, bcb, comex, comtrade, gcp, core, monitor}` packages.

## Step 5 — Propose a plan

After presenting the report, propose a **prioritised refactoring plan** in order of risk:

1. List the top 3 functions/files to tackle first (🔴 items)
2. Estimate effort per item (small/medium/large)
3. Ask: *"Which item would you like to tackle first, or should I start with the highest-risk one?"*

## Important constraints

- **Do not auto-fix.** Every change must be proposed and approved explicitly.
- **The custom Dash frontend was removed and replaced by a live React SPA (`frontend/`) + Flask `webapi` (`src/embrapa_dashboard/webapi/`).** There is no `dashboard/` package or `GoldRepository` class in the tree today — do not expect them, and there is no pending reconstruction to revisit. This audit's Python scope is the ingestion/transform backend **plus** the `webapi`/serving Python (already covered by `test_webapi_*` / `test_serving`); the React frontend has its own Vitest harness.
- **dbt SQL is out of scope** for this audit — use `make dbt-test` + `sqlfluff` for SQL quality.
