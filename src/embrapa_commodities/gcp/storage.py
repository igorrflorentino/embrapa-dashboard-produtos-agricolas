"""GCS landing-zone helpers."""

from __future__ import annotations

import logging
from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

logger = logging.getLogger(__name__)


def ensure_bucket(client: storage.Client, bucket_name: str, location: str) -> storage.Bucket:
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        logger.info("Creating GCS bucket gs://%s (%s, uniform IAM)", bucket_name, location)
        new_bucket = storage.Bucket(client, name=bucket_name)
        new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        return client.create_bucket(new_bucket, location=location)

    # Bucket already exists — ensure uniform bucket-level access is on.
    bucket.reload()
    if not bucket.iam_configuration.uniform_bucket_level_access_enabled:
        logger.info(
            "Upgrading gs://%s to uniform bucket-level access (IAM only).", bucket_name
        )
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
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
