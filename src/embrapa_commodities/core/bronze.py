"""Shared Bronze-layer landing primitive (source-agnostic).

Every ingestion pipeline ends the same way: take the extracted, string-typed
DataFrame, land it as Parquet in the GCS landing zone under a deterministic
``run=<ts>`` path, then append it to its BigQuery Bronze table with an
explicit schema and the partition/cluster keys that match Silver's dedupe.
That tail is identical across IBGE and both BCB pipelines — only the source
name, table, object basename, schema and cluster keys differ. It lives here so
the source modules stay focused on extraction.

What does NOT live here (see ``core/__init__`` docstring): extraction logic,
the delta-start lookup, dataset creation. ``ensure_dataset`` in particular is
left to the caller because BCB must create the dataset *before* extraction (the
delta-start lookup queries the Bronze table); folding it in here would force a
redundant call or a reorder. The caller owns dataset lifecycle; this primitive
owns the GCS-land + BQ-load tail.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.config import Settings
from embrapa_commodities.gcp.bigquery import load_dataframe
from embrapa_commodities.gcp.storage import ensure_bucket, upload_dataframe_as_parquet


def land_and_load(
    df: pd.DataFrame,
    *,
    settings: Settings,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    source: str,
    table: str,
    object_basename: str,
    destination: str,
    schema: list[bigquery.SchemaField],
    clustering_fields: list[str],
    partitioning_field: str = "ingestion_timestamp",
    run_id: str | None = None,
) -> str:
    """Land a Bronze DataFrame in GCS, then append it to BigQuery. Returns ``destination``.

    Assumes ``df`` is non-empty and already string-typed with an
    ``ingestion_timestamp`` column — the empty-fetch short-circuit stays in
    each pipeline so this primitive never lands empty Parquet.

    The GCS object lands at
    ``{gcs_landing_prefix}/{source}/{table}/run={run_id}/{object_basename}.parquet``.
    Pass ``run_id`` when it must match a timestamp already stamped on the rows
    (IBGE shares one instant between the ``ingestion_timestamp`` column and the
    ``run=`` path so reconciliation is unambiguous); leave it ``None`` to mint a
    fresh UTC stamp here.

    ``partitioning_field`` and ``clustering_fields`` are forwarded verbatim to
    ``load_dataframe`` and only take effect on initial table creation.
    """
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    object_name = (
        f"{settings.gcs_landing_prefix}/{source}/{table}/run={run_id}/{object_basename}.parquet"
    )
    upload_dataframe_as_parquet(storage_client, settings.gcs_bucket, object_name, df)

    load_dataframe(
        bq_client,
        df,
        destination,
        schema,
        time_partitioning_field=partitioning_field,
        clustering_fields=clustering_fields,
    )
    return destination
