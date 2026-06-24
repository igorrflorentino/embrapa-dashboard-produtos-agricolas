#!/usr/bin/env node
/**
 * Block Dangerous Commands – PreToolUse Hook for Bash/PowerShell
 *
 * Adapted from karanb192/claude-code-hooks for the embrapa-dashboard-commodities
 * project. Blocks destructive patterns BEFORE Claude Code executes them.
 *
 * Additions over the original:
 *   • GCP patterns  – bq rm, gcloud projects delete, gcloud run services delete
 *   • dbt patterns  – unguarded `dbt run --target prod` without --full-refresh
 *   • Docker prune  – docker system prune / docker volume prune
 *
 * SAFETY_LEVEL: 'critical' | 'high' | 'strict'
 *   critical – Only catastrophic: rm -rf ~, dd to disk, fork bombs
 *   high     – + risky: force push main, secrets exposure, git reset --hard, GCP deletes
 *   strict   – + cautionary: any force push, sudo rm, docker prune
 *
 * Logs to: ~/.claude/hooks-logs/
 *
 * Setup in .claude/settings.json:
 * {
 *   "hooks": {
 *     "PreToolUse": [{
 *       "matcher": "Bash",
 *       "hooks": [{ "type": "command", "command": "node scripts/claude-hooks/block-dangerous-commands.js" }]
 *     }]
 *   }
 * }
 */

const fs = require('fs');
const path = require('path');

const SAFETY_LEVEL = 'high';

const LEVEL_ORDER = { critical: 0, high: 1, strict: 2 };

const PATTERNS = [
  // ── CRITICAL – Catastrophic, unrecoverable ──────────────────────────────
  { level: 'critical', id: 'rm-home',          regex: /\brm\s+(-.+\s+)*["']?~\/?["']?(\s|$|[;&|])/,                        reason: 'rm targeting home directory' },
  { level: 'critical', id: 'rm-home-var',      regex: /\brm\s+(-.+\s+)*["']?\$HOME["']?(\s|$|[;&|])/,                      reason: 'rm targeting $HOME' },
  { level: 'critical', id: 'rm-home-trailing', regex: /\brm\s+.+\s+["']?(~\/?|\$HOME)["']?(\s*$|[;&|])/,                   reason: 'rm with trailing ~/ or $HOME' },
  { level: 'critical', id: 'rm-root',          regex: /\brm\s+(-.+\s+)*\/(\*|\s|$|[;&|])/,                                 reason: 'rm targeting root filesystem' },
  { level: 'critical', id: 'rm-system',        regex: /\brm\s+(-.+\s+)*\/(etc|usr|var|bin|sbin|lib|boot|dev|proc|sys)(\/|\s|$)/, reason: 'rm targeting system directory' },
  { level: 'critical', id: 'rm-cwd',           regex: /\brm\s+(-.+\s+)*(\.\/?\s|\.\/\*|\*\s)(\s|$|[;&|])/,                 reason: 'rm deleting current directory contents' },
  { level: 'critical', id: 'dd-disk',          regex: /\bdd\b.+of=\/dev\/(sd[a-z]|nvme|hd[a-z]|vd[a-z]|xvd[a-z])/,        reason: 'dd writing to disk device' },
  { level: 'critical', id: 'mkfs',             regex: /\bmkfs(\.\w+)?\s+\/dev\/(sd[a-z]|nvme|hd[a-z]|vd[a-z])/,            reason: 'mkfs formatting disk' },
  { level: 'critical', id: 'fork-bomb',        regex: /:\(\)\s*\{.*:\s*\|\s*:.*&/,                                         reason: 'fork bomb detected' },

  // ── HIGH – Significant risk, data loss, security ────────────────────────
  { level: 'high', id: 'curl-pipe-sh',         regex: /\b(curl|wget)\b.+\|\s*(ba)?sh\b/,                                  reason: 'piping URL to shell (RCE risk)' },
  { level: 'high', id: 'force-push-main',      regex: /\bgit\s+push\s+.*--force.*\b(main|master|prod)\b/,                  reason: 'force push to protected branch' },
  { level: 'high', id: 'force-push-main-2',    regex: /\bgit\s+push\s+.*\b(main|master|prod)\b.*--force/,                  reason: 'force push to protected branch' },
  { level: 'high', id: 'git-reset-hard',       regex: /\bgit\s+reset\s+--hard\b/,                                         reason: 'git reset --hard loses uncommitted work' },
  { level: 'high', id: 'git-clean-fd',         regex: /\bgit\s+clean\s+.*-[a-zA-Z]*f[a-zA-Z]*d/,                          reason: 'git clean -fd removes untracked files & dirs' },
  { level: 'high', id: 'chmod-777',            regex: /\bchmod\s+(-R\s+)?777\b/,                                          reason: 'chmod 777 is a security risk' },
  { level: 'high', id: 'env-print',            regex: /\b(printenv|env\s*$|set\s*$)\b/,                                   reason: 'dumping all environment variables' },
  { level: 'high', id: 'cat-env',              regex: /\bcat\s+.*\.env\b/,                                                reason: 'printing .env contents to stdout' },

  // ── HIGH – GCP-specific (embrapa project) ───────────────────────────────
  { level: 'high', id: 'bq-rm',               regex: /\bbq\s+(rm|remove)\b/,                                              reason: 'bq rm deletes BigQuery datasets/tables' },
  { level: 'high', id: 'bq-drop',             regex: /\bbq\s+query\b.*\bDROP\s+(TABLE|DATASET|SCHEMA)\b/i,                 reason: 'DROP via bq query deletes BigQuery objects' },
  { level: 'high', id: 'gcloud-delete-proj',   regex: /\bgcloud\s+projects\s+delete\b/,                                   reason: 'gcloud projects delete is catastrophic' },
  { level: 'high', id: 'gcloud-delete-svc',    regex: /\bgcloud\s+run\s+services\s+delete\b/,                             reason: 'gcloud run services delete removes Cloud Run service' },
  // The ingestion Job, its schedulers, the COMTRADE secret, the runtime SAs and the
  // alert policies are equally destructive prod surface this repo provisions: deleting
  // the Job/scheduler silently stops nightly Bronze refresh; the secret breaks Comtrade
  // ingest (INFRA-2). Mirror the services-delete guard for each.
  { level: 'high', id: 'gcloud-delete-job',    regex: /\bgcloud\s+run\s+jobs\s+delete\b/,                                 reason: 'gcloud run jobs delete removes the ingestion Job (stops nightly Bronze)' },
  { level: 'high', id: 'gcloud-delete-sched',  regex: /\bgcloud\s+scheduler\s+jobs\s+delete\b/,                           reason: 'gcloud scheduler jobs delete removes a nightly/reconcile trigger' },
  { level: 'high', id: 'gcloud-delete-secret', regex: /\bgcloud\s+secrets\s+delete\b/,                                    reason: 'gcloud secrets delete removes a prod secret (e.g. the COMTRADE key)' },
  { level: 'high', id: 'gcloud-delete-sa',     regex: /\bgcloud\s+iam\s+service-accounts\s+delete\b/,                     reason: 'gcloud iam service-accounts delete removes a runtime SA' },
  { level: 'high', id: 'gcloud-delete-alert',  regex: /\bgcloud\s+(alpha\s+|beta\s+)?monitoring\s+policies\s+delete\b/,    reason: 'gcloud monitoring policies delete removes an alert policy' },
  { level: 'high', id: 'gcloud-delete-bucket', regex: /\b(gcloud\s+storage|gsutil)\s+(rm|rb)\s+.*gs:\/\//,                 reason: 'deleting GCS bucket or objects' },
  { level: 'high', id: 'gsutil-rm-r',          regex: /\bgsutil\s+(-m\s+)?rm\s+(-r\s+)?gs:\/\//,                          reason: 'recursive GCS deletion' },

  // ── HIGH – dbt-specific ─────────────────────────────────────────────────
  // Lookaheads (not a fixed `--target prod … then --full-refresh` order) so the flag
  // order doesn't matter: `dbt build --full-refresh --target prod` is correctly ALLOWED
  // while `dbt build --target prod` (no refresh) is blocked, regardless of where the
  // flags sit relative to each other (INFRA-2).
  { level: 'high', id: 'dbt-prod-no-refresh',  regex: /\bdbt\s+(run|build)\b(?=.*--target\s+prod\b)(?!.*--full-refresh)/,   reason: 'dbt run on prod without --full-refresh (use make dbt-build-prod)' },

  // ── STRICT – Cautionary ─────────────────────────────────────────────────
  { level: 'strict', id: 'any-force-push',     regex: /\bgit\s+push\s+.*--force\b/,                                       reason: 'any force push can rewrite history' },
  { level: 'strict', id: 'sudo-rm',            regex: /\bsudo\s+rm\b/,                                                    reason: 'sudo rm is risky' },
  { level: 'strict', id: 'docker-prune',       regex: /\bdocker\s+(system|volume|image|container)\s+prune\b/,              reason: 'docker prune removes resources' },
  { level: 'strict', id: 'npm-sudo',           regex: /\bsudo\s+(npm|pip|uv)\b/,                                          reason: 'package managers should not run as root' },
];

// ── Logging ───────────────────────────────────────────────────────────────
const HOME = process.env.HOME || process.env.USERPROFILE || '';
const LOG_DIR = path.join(HOME, '.claude', 'hooks-logs');

function log(data) {
  try {
    if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });
    const file = path.join(LOG_DIR, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    fs.appendFileSync(file, JSON.stringify({ ts: new Date().toISOString(), hook: 'block-dangerous-commands', ...data }) + '\n');
  } catch { /* logging must never break the hook */ }
}

// ── Pure matcher (exported for unit tests) ──────────────────────────────────
// Return the first PATTERN that fires for `command` at the given safety level, or null.
// No I/O — so scripts/ finally has a deterministic, network-free test surface.
function firstMatch(command, level = SAFETY_LEVEL) {
  if (!command) return null;
  const activeLevel = LEVEL_ORDER[level] ?? 1;
  for (const pattern of PATTERNS) {
    if (LEVEL_ORDER[pattern.level] > activeLevel) continue;
    if (pattern.regex.test(command)) return pattern;
  }
  return null;
}

// ── Main ──────────────────────────────────────────────────────────────────
function main() {
  let input = '';
  try {
    input = fs.readFileSync('/dev/stdin', 'utf8');
  } catch {
    // On Windows, stdin might behave differently
    try { input = fs.readFileSync(0, 'utf8'); } catch { /* empty */ }
  }

  let event;
  try { event = JSON.parse(input); } catch {
    log({ status: 'error', reason: 'failed to parse stdin' });
    process.exit(0); // don't block on parse failure
  }

  const toolName = event.tool_name || '';
  const toolInput = event.tool_input || {};
  const command = toolInput.command || toolInput.input || '';

  if (!command) {
    process.exit(0); // nothing to check
  }

  const pattern = firstMatch(command);
  if (pattern) {
    const msg = `🛑 BLOCKED [${pattern.id}]: ${pattern.reason}`;
    log({ status: 'blocked', id: pattern.id, level: pattern.level, command: command.slice(0, 200), reason: pattern.reason });
    // Output JSON to block the tool call
    console.log(JSON.stringify({ decision: 'block', reason: msg }));
    process.exit(0);
  }

  log({ status: 'allowed', command: command.slice(0, 200) });
  process.exit(0);
}

if (require.main === module) main();

module.exports = { PATTERNS, firstMatch, SAFETY_LEVEL };
