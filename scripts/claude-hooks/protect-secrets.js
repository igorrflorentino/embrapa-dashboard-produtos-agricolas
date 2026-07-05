#!/usr/bin/env node
/**
 * Protect Secrets – PreToolUse Hook for Read|Edit|Write|Bash
 *
 * Adapted from karanb192/claude-code-hooks for the embrapa-dashboard-commodities
 * project. Prevents reading, modifying, or exfiltrating sensitive files.
 *
 * Additions over the original:
 *   • GCP service-account keys, gcloud credential cache
 *   • dbt profiles.yml (contains BQ credentials/project-id)
 *   • Bash exfiltration patterns: cat .env, base64, curl/wget posting secrets
 *
 * SAFETY_LEVEL: 'critical' | 'high' | 'strict'
 *   critical – SSH keys, AWS creds, .env files only
 *   high     – + secrets files, env dumps, exfiltration attempts, GCP creds
 *   strict   – + database configs, any config that might contain secrets
 *
 * Logs to: ~/.claude/hooks-logs/
 *
 * Setup in .claude/settings.json:
 * {
 *   "hooks": {
 *     "PreToolUse": [{
 *       "matcher": "Read|Edit|Write|Bash",
 *       "hooks": [{ "type": "command", "command": "node scripts/claude-hooks/protect-secrets.js" }]
 *     }]
 *   }
 * }
 */

const fs = require('fs');
const path = require('path');

const SAFETY_LEVEL = 'high';

const LEVEL_ORDER = { critical: 0, high: 1, strict: 2 };

// ── Allowlist: files explicitly safe to access ────────────────────────────
// These patterns are checked FIRST; matches bypass all sensitive-file rules.
const ALLOWLIST = [
  /\.env\..*\.example$/i,        // *.env.<anything>.example, e.g. .env.prod.example
  /\.env\.example$/i,
  /\.env\.sample$/i,
  /\.env\.template$/i,
  /\.env\.schema$/i,
  /\.env\.defaults$/i,
  /env\.example$/i,
  /example\.env$/i,
  /profiles\.yml\.example$/i,   // dbt template is safe
];

// ── Sensitive file patterns (for Read, Edit, Write tools) ─────────────────
const SENSITIVE_FILES = [
  // CRITICAL
  { level: 'critical', id: 'env-file',           regex: /(?:^|[/\\])\.env(?:\.[^/\\]*)?$/,                  reason: '.env file contains secrets' },
  { level: 'critical', id: 'envrc',              regex: /(?:^|[/\\])\.envrc$/,                              reason: '.envrc (direnv) contains secrets' },
  { level: 'critical', id: 'ssh-private-key',    regex: /(?:^|[/\\])\.ssh[/\\]id_[^/\\]+$/,                 reason: 'SSH private key' },
  { level: 'critical', id: 'ssh-private-key-2',  regex: /(?:^|[/\\])(id_rsa|id_ed25519|id_ecdsa|id_dsa)$/,  reason: 'SSH private key' },
  { level: 'critical', id: 'ssh-authorized',     regex: /(?:^|[/\\])\.ssh[/\\]authorized_keys$/,            reason: 'SSH authorized_keys' },
  { level: 'critical', id: 'aws-credentials',    regex: /(?:^|[/\\])\.aws[/\\]credentials$/,                reason: 'AWS credentials file' },
  { level: 'critical', id: 'aws-config',         regex: /(?:^|[/\\])\.aws[/\\]config$/,                     reason: 'AWS config may contain secrets' },
  { level: 'critical', id: 'kube-config',        regex: /(?:^|[/\\])\.kube[/\\]config$/,                    reason: 'Kubernetes config contains credentials' },
  { level: 'critical', id: 'pem-key',            regex: /\.pem$/i,                                         reason: 'PEM key file' },
  { level: 'critical', id: 'key-file',           regex: /\.key$/i,                                         reason: 'Key file' },
  { level: 'critical', id: 'p12-key',            regex: /\.(p12|pfx)$/i,                                   reason: 'PKCS12 key file' },

  // HIGH
  { level: 'high', id: 'credentials-json',       regex: /(?:^|[/\\])credentials\.json$/i,                  reason: 'Credentials file' },
  { level: 'high', id: 'secrets-file',           regex: /(?:^|[/\\])(secrets?|credentials?)\.(json|ya?ml|toml)$/i, reason: 'Secrets configuration file' },
  { level: 'high', id: 'service-account',        regex: /service[_-]?account.*\.json$/i,                   reason: 'GCP service account key' },
  // This repo names its SA private keys `sa-*-key.json` (e.g. sa-claude-code-web-dev-key.json,
  // sa-web-dashboard-prod-key.json) — the highest-value secret here, not caught by the
  // `service-account` substring rule. Mirrors the `.gitignore` `sa-*.json` pattern.
  { level: 'high', id: 'sa-keyfile',             regex: /(?:^|[/\\])sa[-_].*key.*\.json$/i,                reason: 'GCP service-account key file (sa-*-key.json)' },
  { level: 'high', id: 'gcloud-creds',           regex: /(?:^|[/\\])\.config[/\\]gcloud[/\\].*(credentials|tokens)/i, reason: 'GCloud credentials' },
  { level: 'high', id: 'azure-creds',            regex: /(?:^|[/\\])\.azure[/\\](credentials|accessTokens)/i,  reason: 'Azure credentials' },
  { level: 'high', id: 'docker-config',          regex: /(?:^|[/\\])\.docker[/\\]config\.json$/,            reason: 'Docker config may contain registry auth' },
  { level: 'high', id: 'netrc',                  regex: /(?:^|[/\\])\.netrc$/,                              reason: '.netrc contains credentials' },
  { level: 'high', id: 'npmrc',                  regex: /(?:^|[/\\])\.npmrc$/,                              reason: '.npmrc may contain auth tokens' },
  { level: 'high', id: 'pypirc',                 regex: /(?:^|[/\\])\.pypirc$/,                             reason: '.pypirc may contain PyPI tokens' },

  // HIGH – GCP / dbt-specific (embrapa project)
  { level: 'high', id: 'dbt-profiles',           regex: /(?:^|[/\\])profiles\.yml$/,                        reason: 'dbt profiles.yml contains BQ project/credentials' },
  { level: 'high', id: 'gcp-keyfile',            regex: /(?:^|[/\\])keyfile\.json$/i,                       reason: 'GCP keyfile' },
  { level: 'high', id: 'application-creds',      regex: /application_default_credentials\.json$/i,          reason: 'GCP Application Default Credentials' },

  // STRICT
  { level: 'strict', id: 'db-config',            regex: /(?:^|[/\\])(database|db)\.(json|ya?ml|toml|ini|cfg)$/i,  reason: 'Database configuration file' },
  { level: 'strict', id: 'config-secrets',        regex: /(?:^|[/\\])config\.(json|ya?ml|toml)$/i,          reason: 'Config file may contain secrets' },
];

// ── Bash exfiltration patterns ────────────────────────────────────────────
// These match command strings when the tool is Bash
const EXFIL_PATTERNS = [
  // CRITICAL
  { level: 'critical', id: 'cat-env',            regex: /\bcat\s+.*\.env\b/,                               reason: 'printing .env to stdout exposes secrets' },
  { level: 'critical', id: 'source-env-echo',    regex: /\bsource\s+.*\.env\b.*&&.*\becho\b/,              reason: 'sourcing .env then echoing variables' },

  // HIGH
  { level: 'high', id: 'base64-secrets',         regex: /\bbase64\b.*\.(env|pem|key|p12|pfx)\b/,           reason: 'base64-encoding secret file' },
  { level: 'high', id: 'curl-post-secrets',      regex: /\b(curl|wget)\b.*(-d|--data|-F|--form).*\.(env|pem|key)\b/,  reason: 'HTTP-posting secret file' },
  { level: 'high', id: 'curl-file-upload',       regex: /\b(curl|wget)\b.*@.*\.(env|pem|key|json)\b/,     reason: 'uploading secret file via HTTP' },
  { level: 'high', id: 'printenv',               regex: /\b(printenv|env\s*$|set\s*$)\b/,                  reason: 'dumping all environment variables' },
  { level: 'high', id: 'grep-password',          regex: /\bgrep\b.*(password|secret|token|api.?key)\b.*\.(env|ya?ml|json|toml)\b/i, reason: 'grepping for secrets in config files' },
];

// ── Logging ───────────────────────────────────────────────────────────────
const HOME = process.env.HOME || process.env.USERPROFILE || '';
const LOG_DIR = path.join(HOME, '.claude', 'hooks-logs');

function log(data) {
  try {
    if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });
    const file = path.join(LOG_DIR, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    fs.appendFileSync(file, JSON.stringify({ ts: new Date().toISOString(), hook: 'protect-secrets', ...data }) + '\n');
  } catch { /* logging must never break the hook */ }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function isAllowlisted(filePath) {
  const normalized = filePath.replace(/\\/g, '/');
  return ALLOWLIST.some(re => re.test(normalized));
}

function checkFile(filePath, activeLevel) {
  const normalized = filePath.replace(/\\/g, '/');
  if (isAllowlisted(normalized)) return null;

  for (const pattern of SENSITIVE_FILES) {
    if (LEVEL_ORDER[pattern.level] > activeLevel) continue;
    if (pattern.regex.test(normalized)) {
      return pattern;
    }
  }
  return null;
}

function checkBashCommand(command, activeLevel) {
  for (const pattern of EXFIL_PATTERNS) {
    if (LEVEL_ORDER[pattern.level] > activeLevel) continue;
    if (pattern.regex.test(command)) {
      return pattern;
    }
  }
  return null;
}

// ── Main ──────────────────────────────────────────────────────────────────
function main() {
  let input = '';
  try {
    input = fs.readFileSync('/dev/stdin', 'utf8');
  } catch {
    try { input = fs.readFileSync(0, 'utf8'); } catch { /* empty */ }
  }

  let event;
  try { event = JSON.parse(input); } catch {
    log({ status: 'error', reason: 'failed to parse stdin' });
    process.exit(0);
  }

  const toolName = event.tool_name || '';
  const toolInput = event.tool_input || {};
  const activeLevel = LEVEL_ORDER[SAFETY_LEVEL] ?? 1;

  // ── Check Bash commands for exfiltration ──────────────────────────────
  if (/bash/i.test(toolName)) {
    const command = toolInput.command || toolInput.input || '';
    if (command) {
      const match = checkBashCommand(command, activeLevel);
      if (match) {
        const msg = `🔒 BLOCKED [${match.id}]: ${match.reason}`;
        log({ status: 'blocked', tool: toolName, id: match.id, level: match.level, command: command.slice(0, 200), reason: match.reason });
        console.log(JSON.stringify({ decision: 'block', reason: msg }));
        process.exit(0);
      }
    }
    log({ status: 'allowed', tool: toolName, command: (toolInput.command || '').slice(0, 200) });
    process.exit(0);
  }

  // ── Check file-based tools (Read, Edit, Write) ────────────────────────
  const filePath = toolInput.file_path || toolInput.path || toolInput.file || '';
  if (!filePath) {
    process.exit(0);
  }

  const match = checkFile(filePath, activeLevel);
  if (match) {
    const msg = `🔒 BLOCKED [${match.id}]: ${match.reason} → ${path.basename(filePath)}`;
    log({ status: 'blocked', tool: toolName, id: match.id, level: match.level, file: filePath, reason: match.reason });
    console.log(JSON.stringify({ decision: 'block', reason: msg }));
    process.exit(0);
  }

  log({ status: 'allowed', tool: toolName, file: filePath });
  process.exit(0);
}

if (require.main === module) main();

// Exported for unit tests (no I/O — deterministic, network-free surface).
module.exports = { ALLOWLIST, SENSITIVE_FILES, EXFIL_PATTERNS, isAllowlisted, checkFile, checkBashCommand, SAFETY_LEVEL, LEVEL_ORDER };
