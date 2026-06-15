#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Run dbt with the repo-root .env EXPORTED into the environment first.
#
# Why this wrapper exists: dbt/dbt_project.yml resolves its dataset names and the
# BCB inflation/currency series codes via `env_var('NAME', '<default>')`. Those
# env vars are only read from the *process environment* — a plain `dbt build`
# (or `cd dbt && dbt build`) never reads .env, so dbt silently falls back to the
# baked-in defaults regardless of what .env says. That made `embrapa doctor`
# validate a config the prod build never actually consumed (the documented
# fragile spot: change BCB_INFLATION_SERIES in .env, doctor stays green, but
# gold.val_real_* comes out NULL because dbt still used the old codes).
#
# This wrapper closes that gap: it exports .env (if present) before invoking dbt,
# so the documented single source of truth (.env) actually reaches the build.
# CI has no .env file and sets the same vars explicitly in the workflow env, so
# the no-.env path here is a safe fall-through to those (or to the defaults).
#
# Usage: scripts/dbt-with-env.sh <dbt args...>   e.g. scripts/dbt-with-env.sh build --target prod
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [ -f "$ENV_FILE" ]; then
  # Export every assignment in .env. `set -a` marks all subsequently-set vars for
  # export; sourcing is safe here because the project's .env values are simple
  # KEY=value tokens (comments and blank lines are ignored by the shell).
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

cd "$REPO_ROOT/dbt"
exec uv run dbt "$@"
