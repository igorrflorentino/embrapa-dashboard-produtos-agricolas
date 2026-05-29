"""GCS landing-zone helpers."""

from __future__ import annotations

import logging
from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
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
_BACKUPS_PREFIX = "backups/"

_LIFECYCLE_RULES: list[dict] = [
    # ── landing/ — raw Bronze inputs, archive-at-365d, never delete ────────
    {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {
            "age": 30,
            "matchesStorageClass": ["STANDARD"],
            "matchesPrefix": [_LANDING_PREFIX],
        },
    },
    {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {
            "age": 90,
            "matchesStorageClass": ["NEARLINE"],
            "matchesPrefix": [_LANDING_PREFIX],
        },
    },
    {
        "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
        "condition": {
            "age": 365,
            "matchesStorageClass": ["COLDLINE"],
            "matchesPrefix": [_LANDING_PREFIX],
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


def _apply_protections(bucket: storage.Bucket) -> bool:
    """Idempotently enable uniform IAM, versioning, lifecycle. Returns True if changed."""
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
    desired = {_rule_key(rule) for rule in _LIFECYCLE_RULES}
    if current != desired:
        bucket.lifecycle_rules = _LIFECYCLE_RULES
        changed = True
    return changed


def ensure_bucket(client: storage.Client, bucket_name: str, location: str) -> storage.Bucket:
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
        new_bucket.lifecycle_rules = _LIFECYCLE_RULES
        return client.create_bucket(new_bucket, location=location)

    bucket.reload()
    if _apply_protections(bucket):
        logger.info(
            "Updating gs://%s protections (uniform IAM + versioning + lifecycle)",
            bucket_name,
        )
        bucket.patch()
    return bucket


def upload_dataframe_as_parquet(
    client: storage.Client,
    bucket_name: str,
    object_name: str,
    df: pd.DataFrame,
) -> str:
    """Write a DataFrame to GCS as Parquet without touching the local filesystem."""
    buffer = BytesIO()
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, buffer, compression="snappy")
    buffer.seek(0)

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_file(buffer, content_type="application/octet-stream")
    uri = f"gs://{bucket_name}/{object_name}"
    logger.info("Uploaded %d rows to %s", len(df), uri)
    return uri
