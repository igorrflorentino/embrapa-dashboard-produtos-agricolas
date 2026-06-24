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

## Changing a banco's maturity / note / coverage without a redeploy

The dashboard's per-banco lifecycle metadata — **maturity stage** (`planejado` ·
`desenvolvimento` · `beta` · `estavel` · `manutencao` · `descontinuado`), the
caveat **note**, the planned **date**, and the **coverage** labels — has its
defaults baked in `registries.py` (backend) and `bancos.js` (the SPA). Those are
the source of truth, but editing them needs a rebuild + Cloud Run redeploy.

For the common operational change (e.g. promoting a banco `beta → estavel` once
its backfill lands, or refreshing a coverage label), there is a **Console-managed
override table** — no rebuild, no redeploy:

- `<dataset>.banco_metadata` (`<dataset>` = `BQ_RESEARCH_INPUTS_DATASET`, default
  `research_inputs`; table name = `BQ_BANCO_METADATA_TABLE`, default
  `banco_metadata`). One **sparse** row per banco you have touched: each column is
  an override; a `NULL` column (or no row at all) falls back to the registry
  default. The API merges it into `/api/source-meta`, so the SPA's MaturityTag /
  MaturityBanner / coverage chips reflect the edit.

```sql
-- Promote UN COMTRADE beta → estavel (removes the caveat banner):
MERGE `<project>.research_inputs.banco_metadata` t
USING (SELECT 'un_comtrade' AS banco_id, 'estavel' AS maturity) s
ON t.banco_id = s.banco_id
WHEN MATCHED THEN UPDATE SET maturity = s.maturity, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (banco_id, maturity, updated_at)
  VALUES (s.banco_id, s.maturity, CURRENT_TIMESTAMP());

-- Update only the coverage label (leave maturity on the registry default):
MERGE `<project>.research_inputs.banco_metadata` t
USING (SELECT 'ibge_pam' AS banco_id, '1974 → presente' AS cobertura_years) s
ON t.banco_id = s.banco_id
WHEN MATCHED THEN UPDATE SET cobertura_years = s.cobertura_years, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (banco_id, cobertura_years, updated_at)
  VALUES (s.banco_id, s.cobertura_years, CURRENT_TIMESTAMP());

-- Revert a banco to its registry default (drop the override row):
DELETE FROM `<project>.research_inputs.banco_metadata` WHERE banco_id = 'un_comtrade';
```

Override columns: `maturity`, `maturity_note`, `maturity_date`, `cobertura_years`,
`cobertura_atualizacao`, `cobertura_granularidade`. Notes:
- Changes take effect within the classification cache TTL
  (`CACHE_CLASSIFICATION_TIMEOUT`, ~30s) — no redeploy, no invalidation needed.
- The table auto-creates on the **first `/api/source-meta` read**
  (`routes._ensure_banco_metadata_table`, idempotent). The prod web SA
  `sa-web-dashboard-prod` already has WRITER on `research_inputs`.
- `maturity` must be one of the six stage ids above (an unknown id falls back to
  `planejado` rendering in the SPA). Keep the registry the long-term source of
  truth: fold a lasting change back into `registries.py` + `bancos.js` at the next
  release so the default and the override agree.

## IAP author verification — set `IAP_AUDIENCE` in prod

Curation writes attribute every edit to a person (`edited_by`). That author can
come from two places, and **which one is active depends on `IAP_AUDIENCE`**:

- **`IAP_AUDIENCE` set** (production): the author is read from the **signed
  `X-Goog-IAP-JWT-Assertion`**, cryptographically verified against this
  audience. A direct request to the backend cannot forge the audit author, and
  an ingress misconfiguration (e.g. an accidentally public service) fails
  closed.
- **`IAP_AUDIENCE` unset**: the in-app JWT double-check is **skipped**. With Cloud
  Run **direct IAP** enabled (the prod posture), the platform still authenticates
  every request and **overwrites** the `X-Goog-Authenticated-User-Email` header, so
  author capture stays trustworthy — the in-app check is defense-in-depth. The
  header is only spoofable when IAP is **not** in front (e.g. local dev), which is
  why this mode is paired with `CURATION_DEV_AUTHOR` for local dev only.

Operator steps (one-time per deployment):

1. Get the audience string: Console → Security → Identity-Aware Proxy → ⋮ on the
   **Cloud Run resource** → "Get JWT audience code" (the direct Cloud Run IAP form).
   *(Only in the future external-LB + IAP topology would it instead take the form
   `/projects/<PROJECT_NUMBER>/global/backendServices/<BACKEND_SERVICE_ID>`.)*
2. Set `IAP_AUDIENCE=<that string>` in the `.env` used for deploys —
   `deploy/webapi/deploy.sh` forwards it to the Cloud Run Service — and run
   `make webapi-deploy`.
3. Verify: a curation save in prod records the IAP identity; with a wrong
   audience the write is rejected rather than silently mis-attributed.

Details: `src/embrapa_commodities/serving/iap.py` and
[`docs/auth_architecture.md`](auth_architecture.md).

## Activating curation in prod (one-time) and keeping it built

> ⚠️ **FROZEN — Curadoria postponed to the "Versão Futura" roadmap phase (2026-06).**
> The curation/enrichment feature is partially built, not yet validated, and **hidden
> from the dashboard UI** (its topnav perspectives in `frontend/src/ui/views.js` and the
> "Engenharia de atributos" sidebar editor in `AppShell.jsx` are commented out behind
> FROZEN banners). The app runs fully decoupled from it. **Do not activate it in prod**
> until the feature is revived and validated — the steps below are kept for that future
> reactivation.

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

## Triaging user feedback ("Reportar problema")

The dashboard's **Reportar problema** button writes each report (bug / dúvida / sugestão)
to the append-only `research_inputs.feedback_log` BigQuery table (auto-created on first
write), with the submitter captured from IAP and a permalink to the current view/filters
attached. Triage by querying the table:

```bash
bq query --use_legacy_sql=false \
  "SELECT submitted_at, category, submitted_by, message, url, issue_url
   FROM \`${GCP_PROJECT_ID}.research_inputs.feedback_log\`
   ORDER BY submitted_at DESC LIMIT 50"
```

Reply to the reporter directly — their e-mail is the `submitted_by` column.

**Closing the loop with GitHub (optional).** Each report is ALSO opened as a GitHub issue
(labelled `feedback` + category) when the service has `FEEDBACK_GITHUB_REPO` (`owner/name`)
**and** the `FEEDBACK_GITHUB_TOKEN` secret. The forward is best-effort — if GitHub is
unreachable the report is still durably in BigQuery (`issue_url` then null), never lost or
blocked.

Wire it up (one-time):

1. Create a **fine-grained** GitHub token scoped to **only** that repo with **Issues:
   Read and write** (not a broad classic PAT), then store it in Secret Manager:

   ```bash
   printf '%s' "<TOKEN>" | gcloud secrets create feedback-github-token \
     --data-file=- --project="$GCP_PROJECT_ID"
   gcloud secrets add-iam-policy-binding feedback-github-token \
     --member="serviceAccount:sa-web-dashboard-prod@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor" --project="$GCP_PROJECT_ID"
   ```

2. Set `FEEDBACK_GITHUB_REPO` in the deploy `.env` (it is in the deploy allowlist). The token
   is mounted automatically: `deploy/webapi/deploy.sh` adds
   `--set-secrets FEEDBACK_GITHUB_TOKEN=feedback-github-token:latest` whenever the secret
   exists (override the name with `FEEDBACK_GITHUB_TOKEN_SECRET`), so a routine redeploy
   **keeps** the loop active — it is never a plaintext env var.

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
