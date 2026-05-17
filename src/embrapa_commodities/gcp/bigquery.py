"""BigQuery Bronze-layer helpers — explicit schemas, no autodetect."""

from __future__ import annotations

import logging

import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)


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

    if existing.location.upper() != location.upper():
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
) -> None:
    """Append a DataFrame to a Bronze table with an explicit schema.

    Explicit schema is intentional: autodetect causes silent drift across runs.
    """
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        schema=schema,
        source_format=bigquery.SourceFormat.PARQUET,
    )
    logger.info("Loading %d rows into %s", len(df), destination)
    job = client.load_table_from_dataframe(df, destination, job_config=job_config)
    job.result()
