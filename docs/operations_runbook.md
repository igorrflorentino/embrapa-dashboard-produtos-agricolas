# Operations Runbook

Occasional, get-it-right operational procedures for the prod deployment — the
things you don't do every day and that bite you on a fresh machine. Day-to-day
commands live in [`README.md`](../README.md) / [`CLAUDE.md`](../CLAUDE.md); this
is the "how do I safely do X against prod" reference.

## Managing curators (who may save curation edits)

The curation write endpoints (`POST /api/curation/*`) are gated by an
**authorization allowlist**, distinct from IAP authentication. The effective
allowlist is the **union** of:

- the `CURATION_ALLOWED_EMAILS` env var (comma-separated), and
- the Console-managed BigQuery table `<dataset>.curators`
  (`<dataset>` = `BQ_RESEARCH_INPUTS_DATASET`, default `research_inputs`; table
  name = `BQ_CURATORS_TABLE`, default `curators`).

If **both** are empty/absent, any IAP-authenticated caller may curate (open mode).

**Add/remove a curator without a redeploy** — edit the table in the BigQuery
Console (or via SQL). No deploy, no code change:

```sql
-- add
INSERT INTO `<project>.research_inputs.curators` (email, added_by, added_at)
VALUES ('new.curator@embrapa.br', 'you@embrapa.br', CURRENT_TIMESTAMP());

-- remove
DELETE FROM `<project>.research_inputs.curators` WHERE email = 'old@embrapa.br';

-- list current
SELECT email FROM `<project>.research_inputs.curators` ORDER BY email;
```

Notes:
- Changes take effect within the classification cache TTL
  (`CACHE_CLASSIFICATION_TIMEOUT`, ~30s) — no instant invalidation needed.
- Emails are matched case-insensitively (lower + trim).
- The table auto-creates on the **first curation write attempt**: the curation
  POST authorization path (`routes._authorize_curator`) calls
  `serving.curation.ensure_curators_table` (idempotent), so it exists for the
  Console INSERT above the first time anyone tries to save an edit. The runtime SA
  needs write access to the dataset to create it — the prod web SA
  `sa-web-dashboard-prod` already has WRITER on `research_inputs`. (If you prefer
  to create it up front, before any write, run the INSERT against the dataset and
  it self-heals, or call the helper directly.)
- Curation writes also accept an optional client `change_id` (idempotency key):
  a retried/double-clicked save reusing the same key is a no-op, not a duplicate
  audit row.

## IAP author verification — set `IAP_AUDIENCE` in prod

Curation writes attribute every edit to a person (`edited_by`). That author can
come from two places, and **which one is active depends on `IAP_AUDIENCE`**:

- **`IAP_AUDIENCE` set** (production): the author is read from the **signed
  `X-Goog-IAP-JWT-Assertion`**, cryptographically verified against this
  audience. A direct request to the backend cannot forge the audit author, and
  an ingress misconfiguration (e.g. an accidentally public service) fails
  closed.
- **`IAP_AUDIENCE` unset**: the JWT check is **skipped** — the app **fails
  open** to the plaintext `X-Goog-Authenticated-User-Email` header, which any
  caller that can reach the service directly can spoof. This mode exists for
  local dev only (paired with `CURATION_DEV_AUTHOR`).

Operator steps (one-time per deployment):

1. Get the audience string: Console → Security → Identity-Aware Proxy → ⋮ on
   the resource → "Get JWT audience code". Behind a load balancer it has the
   form `/projects/<PROJECT_NUMBER>/global/backendServices/<BACKEND_SERVICE_ID>`.
2. Set `IAP_AUDIENCE=<that string>` in the `.env` used for deploys —
   `deploy/webapi/deploy.sh` forwards it to the Cloud Run Service — and run
   `make webapi-deploy`.
3. Verify: a curation save in prod records the IAP identity; with a wrong
   audience the write is rejected rather than silently mis-attributed.

Details: `src/embrapa_commodities/serving/iap.py` and
[`docs/auth_architecture.md`](auth_architecture.md).

## Activating curation in prod (one-time) and keeping it built

The SCD2 curation view (`dim_code_industrialization_scd2`) is gated by
`var('enable_curation', false)` so a fresh project builds green before the
curation log tables exist. Activating curation in prod is therefore two steps:

1. **One-time prod build with the var** (creates the view in the prod dataset;
   needs the curation log tables to exist first — `make ensure-curation`
   provisions them, though the per-code and flow-market logs also auto-create on
   first write):

   ```bash
   cd dbt && uv run dbt build --target prod --vars 'enable_curation: true'
   ```

2. **Flip the repo variable `DBT_ENABLE_CURATION` to `true`** (GitHub →
   Settings → Secrets and variables → Actions → Variables). The
   `dbt-build-prod` workflow adds `--vars 'enable_curation: true'` to every
   push-triggered, scheduled, and manual build when this variable is `true` —
   without the flip, merged changes to the SCD2 view (and its schema tests)
   are silently skipped by the automated builds and the prod view drifts from
   `main`.

Local prod builds after activation should also carry the var (e.g. the
`make reconcile` chained build runs plain `dbt build --target prod` — re-run
the command from step 1 afterwards if a curation-view change is pending).

## Backing up prod Gold from a local / dev machine

`embrapa backup-gold` snapshots the Gold tables to
`gs://<bucket>/backups/run=<ts>/`. Two gotchas when running it **locally**
(outside the prod-targeted CI / Makefile path):

1. **It targets the DEV gold dataset by default** — a local `.env` resolves
   `BQ_GOLD_DATASET` to `dbt_dev_gold`, so a bare run snapshots dev, not prod.
   Override with `BQ_GOLD_DATASET=gold`.
2. **The impersonation SA can't write GCS** — the configured
   `GCP_IMPERSONATION_SA` (`sa-secret-reader-prod`) lacks object-write on the
   datalake bucket (403). Clear it so the client uses your own ADC.

Correct standalone local **prod** snapshot:

```bash
BQ_GOLD_DATASET=gold GCP_IMPERSONATION_SA= uv run embrapa backup-gold
```

The prod path `make dbt-build-prod-with-backup` sets the prod target itself, so
this override is only needed for a one-off local backup. `embrapa doctor` warns
when the latest snapshot is older than `BACKUP_STALENESS_DAYS` (default 14).

## Destructive-command safety hooks

[`scripts/claude-hooks/block-dangerous-commands.js`](../scripts/claude-hooks/block-dangerous-commands.js)
is a `PreToolUse` hook (registered in `.claude/settings.json`) that blocks
destructive command patterns before execution, at `SAFETY_LEVEL = 'high'`.
Relevant gated patterns:

- `bq rm` and `bq query … DROP {TABLE,DATASET,SCHEMA}` — BigQuery deletion
- `gcloud run services delete` — Cloud Run service deletion
- `gcloud storage rm … gs://…` / `gsutil rm` — GCS bucket/object deletion
- `gcloud projects delete`, force-push to `main`/`master`/`prod`, `rm -rf ~`,
  `dd` to a disk device, etc.

Implication: **deleting BigQuery datasets, Cloud Run services, or GCS objects is
blocked for assistants/automation in this repo and must be run manually** in your
own shell. Not gated: `gcloud run revisions delete` (only `services delete` is) —
and note it takes one revision per invocation, not a list. To lift the hook,
remove its entry from `.claude/settings.json` and restart the session.
