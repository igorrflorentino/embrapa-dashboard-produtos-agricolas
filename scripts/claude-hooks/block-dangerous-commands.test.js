// Tests for the block-dangerous-commands PreToolUse hook. Pure-matcher only, no I/O —
// runs network-free via `node --test scripts/claude-hooks/`. Gives scripts/ its first
// automated coverage (TEST-3) and locks the two regex fixes (INFRA-1, INFRA-2).

const { test } = require('node:test');
const assert = require('node:assert');

const { firstMatch } = require('./block-dangerous-commands.js');

const blockedId = (cmd, level) => {
  const m = firstMatch(cmd, level);
  return m ? m.id : null;
};

test('INFRA-1: mkfs.<type> formatting a disk is blocked (the \\w typo let it through)', () => {
  // The form one actually types — mkfs requires a filesystem type.
  assert.strictEqual(blockedId('mkfs.ext4 /dev/sda'), 'mkfs');
  assert.strictEqual(blockedId('mkfs.xfs /dev/sdb'), 'mkfs');
  assert.strictEqual(blockedId('sudo mkfs.ext4 /dev/nvme0n1'), 'mkfs');
  // The bare form (no suffix) must still match.
  assert.strictEqual(blockedId('mkfs /dev/sda'), 'mkfs');
});

test('INFRA-2: dbt prod build guard is flag-order independent', () => {
  // Unguarded prod build → blocked, both flag orders.
  assert.strictEqual(blockedId('dbt build --target prod'), 'dbt-prod-no-refresh');
  assert.strictEqual(blockedId('dbt run --target prod'), 'dbt-prod-no-refresh');
  // --full-refresh present → ALLOWED, regardless of where it sits (the false-positive bug).
  assert.strictEqual(blockedId('dbt build --full-refresh --target prod'), null);
  assert.strictEqual(blockedId('dbt build --target prod --full-refresh'), null);
  // A dev-target build is never the prod guard's business.
  assert.strictEqual(blockedId('dbt build --target dev'), null);
});

test('a benign command is not blocked', () => {
  assert.strictEqual(firstMatch('ls -la && git status'), null);
  assert.strictEqual(firstMatch(''), null);
});

test('safety level gates strict-only rules', () => {
  // `docker system prune` is a STRICT rule — inactive at the default `high` level.
  assert.strictEqual(blockedId('docker system prune', 'high'), null);
  assert.strictEqual(blockedId('docker system prune', 'strict'), 'docker-prune');
});

// ── GCP delete rules: one positive (should-block) + one negative (safe read-only)
// per rule. These are the hook's load-bearing purpose; the bucket-delete and
// bq-global-flag bypasses slipped through precisely because they were untested.

test('bq-rm blocks deletes, incl. global flags before the verb; read-only bq passes', () => {
  assert.strictEqual(blockedId('bq rm -t ds.tbl'), 'bq-rm');
  assert.strictEqual(blockedId('bq remove ds.tbl'), 'bq-rm');
  // Global flags between `bq` and `rm` — the bypass this fix closes.
  assert.strictEqual(blockedId('bq --project_id=embrapa rm -t ds.tbl'), 'bq-rm');
  assert.strictEqual(blockedId('bq --location US rm -r -d ds'), 'bq-rm');
  // Read-only bq commands must NOT be blocked.
  assert.strictEqual(blockedId('bq ls ds'), null);
  assert.strictEqual(blockedId('bq show ds.tbl'), null);
  assert.strictEqual(blockedId('bq --project_id=embrapa ls'), null);
});

test('bq-drop blocks DROP/DELETE/TRUNCATE via bq query, incl. global flags; SELECT passes', () => {
  assert.strictEqual(blockedId('bq query --use_legacy_sql=false "DROP TABLE gold.t"'), 'bq-drop');
  assert.strictEqual(blockedId('bq query "DROP DATASET gold"'), 'bq-drop');
  assert.strictEqual(blockedId('bq --project_id=X query "DROP TABLE gold.t"'), 'bq-drop');
  assert.strictEqual(blockedId('bq query "DELETE FROM gold.gold_pevs_production WHERE 1=1"'), 'bq-drop');
  assert.strictEqual(blockedId('bq query "TRUNCATE TABLE gold.gold_pevs_production"'), 'bq-drop');
  // A read-only SELECT via bq query is fine.
  assert.strictEqual(blockedId('bq query --use_legacy_sql=false "SELECT count(*) FROM gold.t"'), null);
});

test('gcloud-delete-proj blocks project delete; project list/describe pass', () => {
  assert.strictEqual(blockedId('gcloud projects delete embrapa-dashboard-commodities'), 'gcloud-delete-proj');
  assert.strictEqual(blockedId('gcloud projects list'), null);
  assert.strictEqual(blockedId('gcloud projects describe embrapa-dashboard-commodities'), null);
});

test('gcloud-delete-svc blocks Cloud Run service delete; run services list passes', () => {
  assert.strictEqual(blockedId('gcloud run services delete embrapa-dashboard'), 'gcloud-delete-svc');
  assert.strictEqual(blockedId('gcloud run services list'), null);
  assert.strictEqual(blockedId('gcloud run services describe embrapa-dashboard'), null);
});

test('gcloud-delete-job blocks Cloud Run job delete; jobs list passes', () => {
  assert.strictEqual(blockedId('gcloud run jobs delete ingestion'), 'gcloud-delete-job');
  assert.strictEqual(blockedId('gcloud run jobs list'), null);
});

test('gcloud-delete-sched blocks scheduler job delete; scheduler list passes', () => {
  assert.strictEqual(blockedId('gcloud scheduler jobs delete nightly-ingest'), 'gcloud-delete-sched');
  assert.strictEqual(blockedId('gcloud scheduler jobs list'), null);
});

test('gcloud-delete-secret blocks secret delete; secrets list/versions access passes', () => {
  assert.strictEqual(blockedId('gcloud secrets delete comtrade-key'), 'gcloud-delete-secret');
  assert.strictEqual(blockedId('gcloud secrets list'), null);
  assert.strictEqual(blockedId('gcloud secrets versions access latest --secret=comtrade-key'), null);
});

test('gcloud-delete-sa blocks service-account delete; iam list passes', () => {
  assert.strictEqual(blockedId('gcloud iam service-accounts delete sa-web-dashboard-prod@x.iam.gserviceaccount.com'), 'gcloud-delete-sa');
  assert.strictEqual(blockedId('gcloud iam service-accounts list'), null);
});

test('gcloud-delete-alert blocks monitoring policy delete (incl. alpha/beta); policies list passes', () => {
  assert.strictEqual(blockedId('gcloud monitoring policies delete POLICY_ID'), 'gcloud-delete-alert');
  assert.strictEqual(blockedId('gcloud alpha monitoring policies delete POLICY_ID'), 'gcloud-delete-alert');
  assert.strictEqual(blockedId('gcloud beta monitoring policies delete POLICY_ID'), 'gcloud-delete-alert');
  assert.strictEqual(blockedId('gcloud monitoring policies list'), null);
});

test('gcloud-delete-bucket blocks gs:// object/bucket removal via rm/rb (incl. alpha/beta); ls passes', () => {
  assert.strictEqual(blockedId('gcloud storage rm gs://b/o'), 'gcloud-delete-bucket');
  assert.strictEqual(blockedId('gcloud storage rb gs://b'), 'gcloud-delete-bucket');
  // alpha/beta variant — a bypass this fix closes.
  assert.strictEqual(blockedId('gcloud alpha storage rm gs://b/o'), 'gcloud-delete-bucket');
  assert.strictEqual(blockedId('gcloud beta storage rm gs://b/o'), 'gcloud-delete-bucket');
  assert.strictEqual(blockedId('gcloud storage ls gs://b'), null);
  assert.strictEqual(blockedId('gcloud storage cp gs://b/o ./local'), null);
});

test('gcloud-delete-bucket-verb blocks `gcloud storage buckets delete` (modern spelling); buckets list passes', () => {
  assert.strictEqual(blockedId('gcloud storage buckets delete my-bucket'), 'gcloud-delete-bucket-verb');
  assert.strictEqual(blockedId('gcloud storage buckets delete gs://my-bucket'), 'gcloud-delete-bucket-verb');
  assert.strictEqual(blockedId('gcloud alpha storage buckets delete my-bucket'), 'gcloud-delete-bucket-verb');
  assert.strictEqual(blockedId('gcloud storage buckets list'), null);
  assert.strictEqual(blockedId('gcloud storage buckets describe my-bucket'), null);
});

test('gsutil rm gs:// deletion is blocked (by either GCS rule); gsutil ls/cp pass', () => {
  // Both `gcloud-delete-bucket` and `gsutil-rm-r` cover recursive GCS deletion; which one
  // fires first depends on flag placement — either is a valid block.
  assert.ok(['gcloud-delete-bucket', 'gsutil-rm-r'].includes(blockedId('gsutil rm -r gs://b/prefix')));
  assert.ok(['gcloud-delete-bucket', 'gsutil-rm-r'].includes(blockedId('gsutil -m rm -r gs://b/prefix')));
  assert.strictEqual(blockedId('gsutil ls gs://b'), null);
  assert.strictEqual(blockedId('gsutil cp gs://b/o ./local'), null);
});

test('env-print blocks only a bare env/printenv/set dump; single-var reads and subcommands pass', () => {
  assert.strictEqual(blockedId('printenv'), 'env-print');
  assert.strictEqual(blockedId('env'), 'env-print');
  assert.strictEqual(blockedId('set'), 'env-print');
  // Single-var reads and a subcommand literally named `env` are NOT dumps.
  assert.strictEqual(blockedId('printenv PATH'), null);
  assert.strictEqual(blockedId('uv run env'), null);
  assert.strictEqual(blockedId('make env'), null);
  assert.strictEqual(blockedId('set -e'), null);
});

test('cat-env blocks .env dumps but allows the safe *.example templates', () => {
  assert.strictEqual(blockedId('cat .env'), 'cat-env');
  assert.strictEqual(blockedId('cat deploy/webapi/.env.prod'), 'cat-env');
  assert.strictEqual(blockedId('cat .env.example'), null);
  assert.strictEqual(blockedId('cat deploy/webapi/.env.prod.example'), null);
});
