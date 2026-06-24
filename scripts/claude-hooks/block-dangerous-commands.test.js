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
