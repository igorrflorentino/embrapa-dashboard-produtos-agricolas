"""BigQuery Bronze-layer helpers — explicit schemas, no autodetect."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)


def latest_reference_date(
    client: bigquery.Client,
    table_fqn: str,
    series_code: str,
    date_format: str = "%d/%m/%Y",
) -> date | None:
    """Return the max `reference_date_str` parsed as DATE for a BCB series.

    Returns None if the table doesn't exist or the series has no rows.
    Used to compute a delta-fetch start year so we don't re-pull 40 years
    of history on every ingestion.
    """
    sql = f"""
        select max(safe.parse_date(@fmt, reference_date_str)) as max_date
        from `{table_fqn}`
        where series_code = @code
    """
    try:
        result = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("fmt", "STRING", date_format),
                    bigquery.ScalarQueryParameter("code", "STRING", series_code),
                ]
            ),
        ).result()
    except NotFound:
        return None
    row = next(iter(result), None)
    return row.max_date if row else None


def ensure_dataset(client: bigquery.Client, dataset_id: str, location: str) -> None:
    try:
        existing = client.get_dataset(dataset_id)
    except NotFound:
        logger.info("Creating dataset %s in %s", dataset_id, location)
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = location
        # 2-day time travel keeps storage costs predictable on append-only bronze.
        dataset.max_time_travel_hours = 48
        client.create_dataset(dataset, timeout=30)
        return

    existing_location = (existing.location or "").upper()
    if existing_location and existing_location != location.upper():
        raise RuntimeError(
            f"Dataset {dataset_id} exists in location {existing.location!r}, "
            f"but BQ_LOCATION is {location!r}. Cross-region loads are not allowed — "
            f"either align BQ_LOCATION, rename the dataset in .env, or drop the "
            f"stale dataset before re-running."
        )


def load_dataframe(
    client: bigquery.Client,
    df: pd.DataFrame,
    destination: str,
    schema: list[bigquery.SchemaField],
    write_disposition: str = "WRITE_APPEND",
    time_partitioning_field: str | None = None,
    clustering_fields: list[str] | None = None,
) -> None:
    """Append a DataFrame to a Bronze table with an explicit schema.

    Explicit schema is intentional: autodetect causes silent drift across runs.

    `time_partitioning_field` and `clustering_fields` are applied only on
    initial table creation — BigQuery does not allow changing them later. If
    the table already exists without partitioning, drop it before re-running.
    """
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        schema=schema,
        source_format=bigquery.SourceFormat.PARQUET,
    )
    if time_partitioning_field:
        job_config.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=time_partitioning_field,
        )
    if clustering_fields:
        job_config.clustering_fields = clustering_fields

    logger.info("Loading %d rows into %s", len(df), destination)
    job = client.load_table_from_dataframe(df, destination, job_config=job_config)
    job.result()
