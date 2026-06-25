# Complete audit — v1.6.0 (post-remediation)

**Date:** 2026-06-24
**Scope:** the **remediated** v1.6.0 codebase (branch `claude/audit-v1.6.0-remediation`, on top of
release `f141d0f`) — a follow-up to the partial `deep_audit_2026-06-24_v1.6.0.md`, intended to
cover all 12 dimensions and confirm the remediation (PR #173) holds.

## Method (honest note)

The planned 12-dimension multi-agent adversarial workflow **could not complete**: across four
launches/resumes it was repeatedly blocked by a **sustained, transient server-side API rate
limit** ("Server is temporarily limiting requests — not your usage limit"). Only the first
partial run (wave 1: security / feedback-feature / correctness-backend) + the completeness
critic ever produced output; every subsequent wave, verify stage, and synthesis failed fast on
the throttle. This is an **infrastructure limit, not a code or quota issue** — it will clear with
time, and the run is **resumable** (`wf_1ac506c9-741`).

This complete pass was therefore conducted as a **direct, engineer-led review** by the author of
the v1.6.0 changes and their remediation, cross-checked against the **seven prior audits**
(2026-06-12 … 2026-06-23, all graded A−/A with 0 critical) that establish the broader codebase
baseline, and against the **full local test suites** (915 pytest / 267 vitest). A fresh,
independent adversarial agent re-run over the "confirmatory" dimensions below is **recommended
once the rate limit clears**.

---

## Executive summary

**Health grade: A−.** Nothing critical or high. The PR #173 remediation is **confirmed to hold**
(every fix verified, see below). One **new low-severity stale-doc** was found and fixed in this
pass. The broader, mature dimensions show no new code-level defects on direct review.

| Severity | Count (new) |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 (DOC-2, fixed) |
| Info | 1 (DATA-1, operator-owed) |

## Confirmation: the PR #173 remediation holds

| Finding | Status | Evidence |
|---|---|---|
| INFRA-1 (deploy loop wipe) | ✅ fixed | `deploy.sh` allowlists `FEEDBACK_GITHUB_REPO` + mounts the token via a guarded `--set-secrets`; `bash -n` clean |
| FB-1 (forward before write) | ✅ fixed | `feedback.py` INSERTs (issue_url NULL) then forwards then UPDATEs; `test_record_feedback_writes_then_stamps_issue_url` green |
| FREEZE-1 (curation residue) | ✅ fixed | `MainScreen.jsx:43` routes `?ip=curation/enrich_*` to a neutral "Versão Futura" notice (read-confirmed); glossary/views/AppShell entry points commented out; eslint+vitest green |
| DEV-1 (JSX divergence) | ✅ fixed | classic JSX runtime in dev **and** build **and** Vitest (`vitest.setup.js` supplies global React); 267 vitest + build green — divergence eliminated, not just tested |
| SEC-1 (issue injection) | ✅ fixed | message fenced + triple-backtick neutralised; `test_forward_to_github_fences_user_message` green |
| SEC-2 (no rate limit) | ✅ fixed | per-author cooldown; `test_feedback_route_cooldown_returns_429` green |
| TEST-1 (forward untested) | ✅ fixed | success-path / ordering / fence / cooldown tests added |
| DOC-1 (secret docs) | ✅ fixed | runbook Secret-Manager recipe + `.env.example` token-scope note |

## New findings

### 🟢 LOW

#### DOC-2 — `CLAUDE.md` still described Curadoria as activatable (now FROZEN) — **fixed in this pass**
- **File:** `CLAUDE.md:22`
- **What/why:** the architecture note read "**Curadoria** … is built; it needs **prod
  activation** — `dbt build --vars 'enable_curation: true'`…", which is stale: the feature was
  **frozen** and hidden (PRs #168/#169). An AI assistant or new dev reading this would wrongly
  treat curation as activatable. (The #173 DOC-1 fix covered the *feedback* secret docs, not this
  curation line — so the complete pass surfaced it.)
- **Fix (applied):** the line now states curation is built but FROZEN/deferred to *Versão Futura*,
  not activatable, with the backend/dbt kept as gated scaffold.

### ℹ️ INFO

- **DATA-1 (operator-owed):** the CHANGELOG "Fixed" grain claims (`commodity_crosswalk` `'ppm'`,
  `comtrade_cpc_value` axis pins) were validated only by `dbt compile`, not a live `dbt build`
  against prod BigQuery — the sandbox has no `*.googleapis.com` network. A `bigquery-debug` round
  should confirm `gold_*` grain uniqueness. (Carried over from the partial audit; unchanged.)

## Dimension coverage (with depth)

**Deep — authored, remediated, and test-verified this session:** `feedback-feature`,
`curation-freeze`, `dev-server-fix`, `infra-ci-deploy` (deploy.sh), the feedback-surface of
`security`, and the feedback portion of `tests-coverage`. No open issues.

**Confirmatory — mature code, unchanged by v1.6.0, resting on 7 prior A−/A audits + a direct
spot-check:** `correctness-backend` (serving SQL is parameterized via `ScalarQueryParameter` — no
injection surfaced), `correctness-frontend`, `data-dbt` (the frozen SCD2 view is gated by
`enable_curation=false`; no other model forces it on), `ingestion`, `architecture-maintainability`,
and `docs-consistency` (beyond DOC-2). No new defects surfaced; these were **not** re-examined by
an independent adversarial agent (the workflow was throttled) — see the recommendation.

## Recommendation

1. **Re-run the full adversarial agent audit when the server rate-limit clears** — resume
   `wf_1ac506c9-741` (waves of 2, 2-lens). This gives the confirmatory dimensions an independent
   machine pass; this report's direct review is a strong but single-reviewer substitute.
2. **DATA-1:** an operator `dbt build` + grain re-check on prod BigQuery.

No code remediation is required from this pass beyond DOC-2 (already applied).
