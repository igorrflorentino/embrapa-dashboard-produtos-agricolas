# UN Comtrade world (all-reporters) backfill — runbook

How to fill the full COMTRADE history at **maximum granularity** (`reporters=all`), the
last remaining gap to "every source at max granularity, commodity-filtered only".
Everything here was measured against live prod BigQuery + verified against the code
(adversarially reviewed). Storage/compute cost is trivial; the only real constraint
is the UN API daily quota (calendar time).

## Current state (measured 2026-06-17)

`silver_comtrade_flows` per-year reporter coverage shows the gap precisely:

| Years | Reporters | Meaning |
|-------|-----------|---------|
| 1989–2021, 2024–2025 | **1** (Brazil, M49 `76`) | Brazil-only — needs the world backfill |
| **2022, 2023** | **165 / 163** (~272k rows each) | Already all-reporters (earlier "all" dev window) |

So the backfill must fetch **35 missing years** at all-reporters. 2022–2023 already
exist and serve as the measured "pilot" — no separate pilot run is needed.

### Prerequisites — status

| Prerequisite | Status |
|---|---|
| Cost guard: `silver_comtrade_flows` incremental | ✅ Live in prod (PR #127, `f29e848`). Only this model reads raw `bronze_comtrade`; `gold`/`serving` read the Silver aggregate. |
| Secret `comtrade-un-key` in Secret Manager | ✅ Exists. |
| IAM grant — Job runtime SA reads the secret | ✅ Done: `sa-data-pipeline-prod` has `roles/secretmanager.secretAccessor` on `comtrade-un-key`. |
| IAM grant — scheduler SA overrides Job args | ✅ Done: `sa-data-pipeline-prod` has `roles/run.jobsExecutorWithOverrides` (+ `run.invoker`) on job `embrapa-ingest-all`. |
| Job has the key mounted | ✅ `COMTRADE_API_KEY` mounted via `secretKeyRef` → `comtrade-un-key`. |
| Job has the all-reporters **scope** | ❌ **Not yet** — the deployed job carries NO `COMTRADE_*` scope env (no `COMTRADE_REPORTERS`), so it would run on `config.py` defaults = `reporters=76` (Brazil). **A redeploy with `COMTRADE_REPORTERS=all` is required for the Job path** (the scope is baked at deploy time). |

## Expected volume / time / cost (measured anchors)

| Metric | Value |
|---|---|
| API calls | ~1,120 base (35 years × 32 reporter-batches of 8) + adaptive splits → **~1,180–1,230** |
| Silver rows (final, all history) | **~4.25M** (2022+2023 reproduce the measured 544,596 exactly; ~3.70M net-new) |
| Bronze rows (final) | **~29.7M** (~7× Silver; breakdown rows) |
| BigQuery added | **~5.9 GB** (~2.7 bronze + ~0.51 silver + ~1.36 gold + ~1.30 serving) → project ~7.7 → **~13.6 GB** |
| GCS raw added | **~3 GB** |
| Storage cost | **< R$ 10/month** (trivial) |
| Time — free key | **~3 days best case**, realistically **3–12 days** (the free-tier daily cap is unverified — historically ~100–500 calls/day + a 1 call/sec throttle; read the real cap off the first run's quota-exhaust point) |
| Time — premium key | **< 1 day** (a few hours) |

The commodity filter (~150 HS6 codes) keeps this ~10× below a naive dense-matrix
estimate; per-chunk rows stay well under the 100k-row/call cap so adaptive splits
rarely fire.

## Path A — LOCAL (recommended to drive the backfill)

Run from the repo root. Fetch the key from Secret Manager into the child process
env only (never printed, never in shell history). The local ADC principal needs
`roles/secretmanager.secretAccessor` on `comtrade-un-key`.

```bash
COMTRADE_API_KEY="$(gcloud secrets versions access latest --secret=comtrade-un-key --project=<GCP_PROJECT_ID>)" \
COMTRADE_REPORTERS=all COMTRADE_START_YEAR=1989 \
uv run embrapa ingest comtrade
```

The inline `COMTRADE_*` vars override `.env`. The run is **resume-aware**: archived
chunks skip, so re-run across days to finish. Use `--full` only to force-refetch
already-archived chunks. An empty `COMTRADE_API_KEY` hard-exits with a clear message.

### Driving it to completion — read the summary, do NOT branch on the exit code

The run is quota-gated and **exits 1 both on quota exhaustion AND on any failed
chunk** (transient error, `ComtradeTruncationError` which recurs identically, a
BigQuery load failure). A blind daily re-run loop would mask a real, recurring
failure forever. So after each run, **read the closing summary**, not `$?`:

- Yellow `COMTRADE quota exhausted` banner → quota; **re-run tomorrow** (expected, not a failure).
- `⚠ N chunk(s) failed` with the per-chunk error list → **a real failure — investigate before re-running.**
- `All N chunks complete` (exit 0) → backfill done.

Progress check (years still at `reporters=1` are pending):

```bash
bq query --use_legacy_sql=false --project_id=<GCP_PROJECT_ID> '
SELECT refYear, COUNT(DISTINCT reporterCode) AS reporters, COUNT(*) AS rows
FROM `<GCP_PROJECT_ID>.bronze.comtrade_flows_raw` GROUP BY refYear ORDER BY refYear'
```

### Prod-safety (the local run writes prod Bronze directly)

- Ingestion has **no dev/prod split** — `ingest comtrade` writes prod `bronze_comtrade`.
  Bronze load is at-least-once: a crash duplicates rows, which is **safe** (Silver
  dedupes by `reporterCode` + `ingestion_timestamp desc`), but it is prod.
- **Do not run the local loop on/around the 15th.** The monthly Job trigger (cron
  `0 4 15`) shares the same UN key; running both the same day splits the one daily
  quota and the Job logs a failure. **Defer wiring the monthly schedule (Path B)
  until the backfill is done.**
- **2022–2023 will likely RE-FETCH (not skip).** Resume keys on a content hash of
  the sorted 8-reporter batch; if the UN reporter set changed since the earlier
  "all" dev run, the batch windows shift and most 2022–2023 chunks re-fetch. Extra
  quota only — correctness is safe (Silver dedupes; orphaned old objects are inert).
  Treat the day-count as a floor. To confirm before committing, list the raw objects
  under `raw/comtrade/comtrade_flows/` and compare basenames.

## Path B — Cloud Run Job (steady-state regime, after the backfill)

`schedule_comtrade.sh` does NOT run the backfill — it creates/updates a **monthly**
Cloud Scheduler trigger (cron `0 4 15 * *`, America/Sao_Paulo) that runs the
`embrapa-ingest-all` job with args overridden to `["comtrade"]`. Monthly is too slow
for the initial backfill (use Path A for that); use Path B for ongoing
current-year + revision absorption once the history is filled.

To make the Job run **all-reporters** (IAM + secret are already in place — see the
prereq table; the job currently lacks the all-reporters scope):

1. In `.env`, set (uncomment) both:
   ```bash
   COMTRADE_KEY_SECRET=comtrade-un-key   # forwards COMTRADE_* scope + mounts the key at deploy
   COMTRADE_REPORTERS=all                # baked into the job env at deploy time
   COMTRADE_START_YEAR=1989
   ```
2. Redeploy so the job env gets `COMTRADE_REPORTERS=all` + the comtrade scope:
   ```bash
   make ingest-job-deploy
   ```
   > The scope is baked at **deploy** time — re-triggering the schedule alone will
   > NOT pick up a `.env` change.
3. Wire the monthly trigger (for steady-state):
   ```bash
   make ingest-job-comtrade-schedule
   ```
4. One-shot manual run (without waiting for cron):
   ```bash
   gcloud run jobs execute embrapa-ingest-all --region <REGION> --project <GCP_PROJECT_ID> --args=comtrade
   ```

> COMTRADE is `in_all=False`: the nightly `ingest all` and `make reconcile` never
> touch it. The only paths are local `ingest comtrade` or this dedicated Job.

## Verification after the backfill

1. **Brazil intact** — `reporterCode = '76'` present every year 1989–2025 (counts in the measured 337–1,628 range).
2. **World coverage complete** — every year shows `reporters` ≫ 1 in BOTH `bronze.comtrade_flows_raw` AND `gold.gold_comtrade_flows`.
3. **Propagate to Silver/Gold/serving** (Bronze-only is refreshed by the ingest):
   ```bash
   make dbt-build-prod-with-backup    # build + Gold snapshot; no --full-refresh needed (Silver is incremental + year-agnostic)
   ```
4. **Value conservation** — `cd dbt && uv run dbt test --select gold_comtrade_flows`.
5. **Confirm the incremental build stayed cheap** — once a couple of backfilled years have landed, check `INFORMATION_SCHEMA.JOBS` for the `silver_comtrade_flows` MERGE's `total_bytes_processed`.
6. **Only then** flip `un_comtrade` `maturity: 'beta'` → `'estavel'` in `frontend/src/ui/bancos.js` — gated on (1)+(2) above AND the conservation test passing.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Daily dbt build query cost (Silver scanning a growing Bronze) | **Mitigated** — `silver_comtrade_flows` is incremental; the daily build scans only the partitions for years with new ingestions. Note: on the LOCAL path many years can land in one quota window, so the next build's `affected_years` may span several years (scan ≈ years-landed × bronze/year) — still bounded and very likely < 1 TB/month, but monitor `INFORMATION_SCHEMA.JOBS`. |
| Quota exhaustion "looks like failure" | Expected; resumable. Read the summary banner, not the exit code (see Path A). |
| Job deployed without all-reporters scope | Verified current gap — set `COMTRADE_REPORTERS=all` + `COMTRADE_KEY_SECRET` in `.env`, then `make ingest-job-deploy` (scope is baked at deploy). |
| `gold`/`serving` are `materialized=table` (full daily rebuild) | Bounded by Silver size (~1–2 GB), not Bronze — cheap today; if Silver grows past several GB, consider making them incremental too. |

## Source references

- `deploy/ingestion/schedule_comtrade.sh` — monthly trigger + prerequisites block
- `deploy/ingestion/deploy.sh` — secret wiring (`--set-secrets`), `COMTRADE_*` scope forwarding gated on `COMTRADE_KEY_SECRET`
- `src/embrapa_dashboard/cli.py` — `ingest comtrade`; COMTRADE is `in_all=False`
- `src/embrapa_dashboard/comtrade/pipeline.py` — `resolve_reporters` (`all` → `list_reporters()`), `_basename` (content-hash resume), `plan_chunks`, `sync_raw`
- `dbt/models/silver/silver_comtrade_flows.sql` — the incremental cost guard
