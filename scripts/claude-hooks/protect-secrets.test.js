// Tests for the protect-secrets PreToolUse hook. Pure-matcher only, no I/O —
// runs network-free via `node --test scripts/claude-hooks/protect-secrets.test.js`.
// Locks the two secret-protection fixes: SA-key files (sa-*-key.json — the repo's
// own convention) are blocked, and *.example templates (incl. .env.prod.example)
// stay readable.

const { test } = require('node:test');
const assert = require('node:assert');

const { checkFile, checkBashCommand, LEVEL_ORDER } = require('./protect-secrets.js');

const HIGH = LEVEL_ORDER.high;
const fileId = (f) => {
  const m = checkFile(f, HIGH);
  return m ? m.id : null;
};

test('SA private-key files (sa-*-key.json, the repo convention) are protected', () => {
  assert.strictEqual(fileId('sa-web-dashboard-prod-key.json'), 'sa-keyfile');
  assert.strictEqual(fileId('scripts/sa-claude-code-web-dev-key.json'), 'sa-keyfile');
  assert.strictEqual(fileId('C:\\repo\\scripts\\sa-ingestion-key.json'), 'sa-keyfile');
  // The classic service-account naming still fires (unchanged).
  assert.strictEqual(fileId('my-service-account.json'), 'service-account');
});

test('a benign source/data file is not protected', () => {
  assert.strictEqual(fileId('src/embrapa_dashboard/config.py'), null);
  assert.strictEqual(fileId('dbt/seeds/comtrade_country.csv'), null);
  // A JSON that merely lives under scripts/ but isn't a key.
  assert.strictEqual(fileId('frontend/package.json'), null);
});

test('.env secret files are blocked but *.example templates are allowed', () => {
  assert.strictEqual(fileId('.env'), 'env-file');
  assert.strictEqual(fileId('deploy/webapi/.env.prod'), 'env-file');
  // The safe committed templates — incl. the .prod.example the deploy docs point to.
  assert.strictEqual(fileId('.env.example'), null);
  assert.strictEqual(fileId('deploy/webapi/.env.prod.example'), null);
  assert.strictEqual(fileId('dbt/profiles.yml.example'), null);
});

test('Bash exfiltration of secrets is still caught', () => {
  const bashId = (c) => {
    const m = checkBashCommand(c, HIGH);
    return m ? m.id : null;
  };
  assert.strictEqual(bashId('cat .env'), 'cat-env');
  assert.strictEqual(bashId('base64 sa-web-dashboard-prod-key.json'), null); // .json not in base64 rule
  assert.strictEqual(bashId('ls -la'), null);
});
