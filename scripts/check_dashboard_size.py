#!/usr/bin/env python
"""Soft 500-LOC ceiling for dashboard modules.

Enforces the guardrail recommended by the 2026-05 codebase audit
(see ``docs/audit_2026-05.md`` § 2.1 and Action item #7): no Python file
under ``src/embrapa_commodities/dashboard/`` should grow past ~500
physical lines without a conscious decision. Two files were already
over the line when the policy was introduced; they are grandfathered
via ``ALLOWLIST`` below.

Wired up as a ``local`` hook in ``.pre-commit-config.yaml``. Pre-commit
passes the staged files as positional args, so an unrelated commit
pays zero overhead — the hook only inspects what's actually being
changed.

Exit codes:
    0  every checked file is within the ceiling (or correctly allowlisted)
    1  at least one file exceeds 500 LOC and is not allowlisted
       (or an allowlisted file dropped under 500 — see "self-pruning"
       behaviour below)

Allowlist policy
----------------
The allowlist is intentionally self-pruning: if an allowlisted file
drops below the ceiling, this script fails with a message asking you
to remove it from ``ALLOWLIST``. That prevents the allowlist from
silently shielding future drift on a file that was successfully
refactored once, then bloated again.

To grandfather a new file (only if a refactor is genuinely out of
scope), add it to ``ALLOWLIST`` *with a one-line comment* explaining
why. Do not add files just to silence the hook — the whole point of
the ceiling is to surface the conversation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Physical-line ceiling (matches `wc -l`). Soft — the hook prints a
# clear message and the contributor decides whether to refactor or
# add to ALLOWLIST.
SOFT_LIMIT = 500

# Only files under this prefix are checked. Pre-commit's ``files:``
# regex already filters most of the time, but we double-check here so
# the script is safe to run manually with arbitrary paths.
WATCHED_PREFIX = "src/embrapa_commodities/dashboard/"

# Files that exceeded the limit when the policy was introduced
# (2026-05 audit), or were grandfathered later with a documented
# justification. Modifications are still permitted, but they cannot
# grow indefinitely — once one is refactored under 500, remove it
# from this list.
#
# Paths use forward slashes to match pre-commit's argv on every OS.
ALLOWLIST: dict[str, str] = {
    # The data-access layer for the dashboard: 4 cached Gold-table
    # snapshots + 14 purpose-built query methods (6 generic slicers used
    # by all 4 primary views, 6 view-specific analytical helpers for
    # Qualidade dos Dados / Geografia, plus metadata + cache internals).
    # Splitting the analytical helpers into a sibling module would
    # require either exposing the private `_cached`/`_T_*` constants or
    # duplicating the cache contract — both worse than keeping the
    # class intentionally dense. The complexity is in the number of
    # methods, not in any individual method (every public method is
    # under 20 LOC of body).
    "src/embrapa_commodities/dashboard/data.py": (
        "Single GoldRepository class with 14 small query methods + "
        "per-table cache internals; splitting would fragment the cache "
        "contract across files. Reviewed in PR for Task #5."
    ),
}


def _normalize(path: str) -> str:
    """Return ``path`` with forward slashes, relative if possible.

    Pre-commit may pass either forward- or back-slashed paths
    depending on platform; ALLOWLIST keys use forward slashes, so
    we normalize once at the boundary.
    """
    return path.replace("\\", "/")


def _count_lines(path: Path) -> int:
    """Count physical lines (matches ``wc -l``)."""
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def check(paths: list[str]) -> int:
    failures: list[str] = []

    for raw in paths:
        rel = _normalize(raw)
        if not rel.startswith(WATCHED_PREFIX):
            continue
        if not rel.endswith(".py"):
            continue

        p = Path(raw)
        if not p.is_file():
            # File was deleted/renamed in the same commit — nothing
            # to enforce.
            continue

        loc = _count_lines(p)
        allowlisted = rel in ALLOWLIST

        if allowlisted and loc <= SOFT_LIMIT:
            failures.append(
                f"{rel} is now {loc} LOC (<= {SOFT_LIMIT}). "
                f"Remove it from ALLOWLIST in scripts/check_dashboard_size.py -- "
                f"the grandfather entry is no longer needed."
            )
            continue

        if not allowlisted and loc > SOFT_LIMIT:
            failures.append(
                f"{rel} is {loc} LOC, exceeds soft {SOFT_LIMIT}-LOC ceiling for "
                f"dashboard modules. Consider extracting callbacks into a separate "
                f"module, or add to ALLOWLIST in scripts/check_dashboard_size.py "
                f"with a comment explaining why."
            )

    if failures:
        print("Dashboard module size check failed:\n", file=sys.stderr)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr)
        print(
            "\nThe 500-LOC ceiling is a soft guardrail from the 2026-05 audit "
            "(docs/audit_2026-05.md, section 2.1). It exists to keep page "
            "modules scannable; large pages should split callbacks/layout/data "
            "into separate modules.",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> int:
    # pre-commit passes staged files as argv; running with no args is
    # a no-op so `pre-commit run check-dashboard-size` on an unrelated
    # commit doesn't spuriously inspect every dashboard file.
    return check(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
