"""GCS landing-zone helpers."""

from __future__ import annotations

import logging
from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

logger = logging.getLogger(__name__)

# Storage-class lifecycle: landing Parquet is rarely re-read after the first
# Silver build. Tier down quickly to slash storage cost without losing audit.
#   age=30   → Nearline (~50% cheaper than Standard, free reads ≥30d)
#   age=90   → Coldline (~70% cheaper than Standard)
#   age=365  → Archive  (~85% cheaper than Standard)
# Non-current versions (created by Object Versioning) are deleted at 30d so
# accidental overwrites can be recovered for a month but don't bloat storage.
_LIFECYCLE_RULES: list[dict] = [
    {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30, "matchesStorageClass": ["STANDARD"]},
    },
    {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 90, "matchesStorageClass": ["NEARLINE"]},
    },
    {
        "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
        "condition": {"age": 365, "matchesStorageClass": ["COLDLINE"]},
    },
    {
        "action": {"type": "Delete"},
        "condition": {"age": 30, "isLive": False},
    },
]


def _apply_protections(bucket: storage.Bucket) -> bool:
    """Idempotently enable uniform IAM, versioning, lifecycle. Returns True if changed."""
    changed = False
    if not bucket.iam_configuration.uniform_bucket_level_access_enabled:
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        changed = True
    if not bucket.versioning_enabled:
        bucket.versioning_enabled = True
        changed = True
    # Compare lifecycle by normalized list of dicts.
    current = [dict(rule) for rule in (bucket.lifecycle_rules or [])]
    if current != _LIFECYCLE_RULES:
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
