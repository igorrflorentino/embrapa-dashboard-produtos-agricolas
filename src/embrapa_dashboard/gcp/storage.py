"""GCS landing-zone helpers."""

from __future__ import annotations

import logging

from google.cloud import storage

logger = logging.getLogger(__name__)

# Storage-class lifecycle.
#
# Two prefixes coexist in the bucket and need different retention:
#
#   landing/  → raw Parquet, rarely re-read after the Silver build. Tier
#               aggressively down to ARCHIVE; never delete (audit trail).
#   backups/  → Gold snapshots. Tier the same way but DELETE at 365d —
#               the chain of snapshots itself is the retention, and old
#               snapshots referencing dropped schemas are not restorable
#               anyway.
#
# Every transition rule is prefix-scoped so the two streams stay
# isolated; without that, the landing→ARCHIVE rule would silently bind to
# backup objects and prevent the 365-day delete from firing.
#
#   age=30   → Nearline (~50% cheaper than Standard, free reads ≥30d)
#   age=90   → Coldline (~70% cheaper than Standard)
#   age=365  → Archive (landing) / Delete (backups)
#
# Non-current versions (created by Object Versioning) are deleted at 30d
# bucket-wide so accidental overwrites can be recovered for a month but
# don't bloat storage.
_LANDING_PREFIX = "landing/"
_DEFAULT_RAW_PREFIX = "raw/"
_BACKUPS_PREFIX = "backups/"


def _build_lifecycle_rules(raw_prefix: str = _DEFAULT_RAW_PREFIX) -> list[dict]:
    """The storage-class lifecycle rule set, scoped to the configured raw prefix.

    The raw-zone prefix is operator-tunable (GCS_RAW_PREFIX / settings.gcs_raw_prefix),
    so the archive-trail tiering must bind to the SAME prefix the raw extracts are
    written under — a hardcoded ``raw/`` would silently leave every raw object at
    STANDARD class forever once an operator overrode the prefix.
    """
    # Both landing/ (legacy filtered Bronze inputs) and the raw zone (two-phase
    # verbatim extracts) hold cold audit-trail Parquet: tier down to ARCHIVE,
    # never delete.
    archive_trail_prefixes = [_LANDING_PREFIX, raw_prefix]
    return [
        # ── landing/ + raw zone — Bronze inputs, archive-at-365d, never delete ─
        {
            "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
            "condition": {
                "age": 30,
                "matchesStorageClass": ["STANDARD"],
                "matchesPrefix": archive_trail_prefixes,
            },
        },
        {
            "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
            "condition": {
                "age": 90,
                "matchesStorageClass": ["NEARLINE"],
                "matchesPrefix": archive_trail_prefixes,
            },
        },
        {
            "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
            "condition": {
                "age": 365,
                "matchesStorageClass": ["COLDLINE"],
                "matchesPrefix": archive_trail_prefixes,
            },
        },
        # ── backups/ — Gold cold-storage, delete-at-365d ──────────────────────
        {
            "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
            "condition": {
                "age": 30,
                "matchesStorageClass": ["STANDARD"],
                "matchesPrefix": [_BACKUPS_PREFIX],
            },
        },
        {
            "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
            "condition": {
                "age": 90,
                "matchesStorageClass": ["NEARLINE"],
                "matchesPrefix": [_BACKUPS_PREFIX],
            },
        },
        {
            "action": {"type": "Delete"},
            "condition": {
                "age": 365,
                "matchesPrefix": [_BACKUPS_PREFIX],
            },
        },
        # ── bucket-wide — non-current version cleanup ─────────────────────────
        {
            "action": {"type": "Delete"},
            "condition": {"age": 30, "isLive": False},
        },
    ]


# Default rule set (raw prefix = "raw/"). ensure_bucket rebuilds this per-call
# from the operator's configured prefix; this constant is the default-prefix form.
_LIFECYCLE_RULES: list[dict] = _build_lifecycle_rules()


def _rule_key(rule: dict) -> tuple:
    """Canonical, order-insensitive identity of a lifecycle rule.

    Reduces a rule to a hashable tuple of only the fields we actually set. GCS
    echoes lifecycle rules back in a normalized shape (reordered keys, occasional
    extra defaults) that rarely dict-equals our hand-written literal — a naive
    `current != _LIFECYCLE_RULES` would therefore patch the bucket on EVERY
    ingestion. Comparing canonical keys makes the idempotency check actually
    short-circuit.
    """
    action = rule.get("action") or {}
    cond = rule.get("condition") or {}
    return (
        action.get("type"),
        action.get("storageClass"),
        cond.get("age"),
        tuple(sorted(cond.get("matchesStorageClass") or [])),
        tuple(sorted(cond.get("matchesPrefix") or [])),
        cond.get("isLive"),
    )


def _normalize_raw_prefix(raw_prefix: str | None) -> str:
    """Coerce the operator-supplied raw prefix to the ``<prefix>/`` lifecycle form.

    ``settings.gcs_raw_prefix`` is a bare prefix (default ``raw``, no trailing
    slash) that raw_object_name joins as ``<prefix>/<source>/...``, so the
    lifecycle ``matchesPrefix`` must carry the trailing slash to match those
    objects. Falls back to the default when unset/blank.
    """
    prefix = (raw_prefix or "").strip().strip("/")
    if not prefix:
        return _DEFAULT_RAW_PREFIX
    return f"{prefix}/"


def _apply_protections(bucket: storage.Bucket, lifecycle_rules: list[dict] | None = None) -> bool:
    """Idempotently enable uniform IAM, versioning, lifecycle. Returns True if changed."""
    if lifecycle_rules is None:
        lifecycle_rules = _LIFECYCLE_RULES
    changed = False
    if not bucket.iam_configuration.uniform_bucket_level_access_enabled:
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        changed = True
    if not bucket.versioning_enabled:
        bucket.versioning_enabled = True
        changed = True
    # Compare lifecycle semantically (canonical keys), not by raw dict equality —
    # see _rule_key. Only patch when the rule SET actually differs.
    current = {_rule_key(dict(rule)) for rule in (bucket.lifecycle_rules or [])}
    desired = {_rule_key(rule) for rule in lifecycle_rules}
    if current != desired:
        bucket.lifecycle_rules = lifecycle_rules
        changed = True
    return changed


def ensure_bucket(
    client: storage.Client,
    bucket_name: str,
    location: str,
    raw_prefix: str | None = None,
) -> storage.Bucket:
    lifecycle_rules = _build_lifecycle_rules(_normalize_raw_prefix(raw_prefix))
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        logger.info(
            "Creating GCS bucket gs://%s (%s, uniform IAM + versioning + lifecycle)",
            bucket_name,
            location,
        )
        new_bucket = storage.Bucket(client, name=bucket_name)
        new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        new_bucket.versioning_enabled = True
        new_bucket.lifecycle_rules = lifecycle_rules
        return client.create_bucket(new_bucket, location=location)

    bucket.reload()
    if _apply_protections(bucket, lifecycle_rules):
        logger.info(
            "Updating gs://%s protections (uniform IAM + versioning + lifecycle)",
            bucket_name,
        )
        bucket.patch()
    return bucket
