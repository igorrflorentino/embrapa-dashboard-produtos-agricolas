"""Bronze pipeline for BCB inflation indices — codes configurable via .env."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.bcb.client import fetch_series
from embrapa_commodities.config import Settings
from embrapa_commodities.gcp.bigquery import ensure_dataset, load_dataframe
from embrapa_commodities.gcp.storage import ensure_bucket, upload_dataframe_as_parquet

logger = logging.getLogger(__name__)

BRONZE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("series_code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("series_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_date_str", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("value_str", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
]


def _extract(settings: Settings) -> pd.DataFrame:
    series_map = settings.inflation_series_map
    if not series_map:
        raise RuntimeError("BCB_INFLATION_SERIES is empty.")

    frames: list[pd.DataFrame] = []
    for code, name in series_map.items():
        df = fetch_series(code, settings.bcb_start_year, settings.bcb_end_year)
        if df.empty:
            continue
        df = df.rename(columns={"data": "reference_date_str", "valor": "value_str"})
        df["series_code"] = code
        df["series_name"] = name
        frames.append(df[["series_code", "series_name", "reference_date_str", "value_str"]])
    if not frames:
        raise RuntimeError("BCB returned no inflation data for the configured window.")
    combined = pd.concat(frames, ignore_index=True)
    combined["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
    return combined


def run(settings: Settings) -> str:
    df = _extract(settings)

    storage_client = storage.Client(project=settings.gcp_project_id)
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    object_name = (
        f"{settings.gcs_landing_prefix}/bcb/{settings.bq_bronze_bcb_inflation_table}/"
        f"run={run_id}/inflation_{settings.bcb_start_year}_{settings.bcb_end_year}.parquet"
    )
    upload_dataframe_as_parquet(storage_client, settings.gcs_bucket, object_name, df)

    bq_client = bigquery.Client(project=settings.gcp_project_id, location=settings.bq_location)
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_bcb_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    destination = f"{dataset_id}.{settings.bq_bronze_bcb_inflation_table}"
    load_dataframe(
        bq_client,
        df,
        destination,
        BRONZE_SCHEMA,
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=["series_code", "reference_date_str"],
    )
    return destination
