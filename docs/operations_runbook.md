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
- The table auto-creates on first use (`serving.curation.ensure_curators_table`);
  the runtime SA needs read access to the dataset (the prod web SA `sa-web-dashboard-prod`
  already has WRITER on `research_inputs`).
- Curation writes also accept an optional client `change_id` (idempotency key):
  a retried/double-clicked save reusing the same key is a no-op, not a duplicate
  audit row.

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
