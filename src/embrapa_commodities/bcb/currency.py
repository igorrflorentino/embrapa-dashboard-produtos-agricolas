"""Bronze pipeline for BCB foreign-exchange series — codes configurable via .env."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.bcb.client import fetch_series
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.gcp.bigquery import ensure_dataset, latest_reference_date, load_dataframe
from embrapa_commodities.gcp.storage import ensure_bucket, upload_dataframe_as_parquet

logger = logging.getLogger(__name__)

# Daily FX rates aren't usually revised, but a 1-month overlap absorbs any
# delayed corrections without re-fetching decades of history.
DELTA_OVERLAP_DAYS = 30

BRONZE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("series_code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("reference_date_str", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("value_str", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
]


def _effective_start_year(
    bq_client: bigquery.Client,
    table_fqn: str,
    code: str,
    configured_start: int,
) -> int:
    last = latest_reference_date(bq_client, table_fqn, code)
    if last is None:
        return configured_start
    # FX is daily, so a 30-day overlap is plenty.
    delta_start = (last.year - 1) if last.month == 1 else last.year
    return max(configured_start, delta_start)


def _extract(
    settings: Settings,
    bq_client: bigquery.Client,
    table_fqn: str,
    *,
    full: bool,
) -> pd.DataFrame:
    series_map = settings.currency_series_map
    if not series_map:
        raise RuntimeError("BCB_CURRENCY_SERIES is empty.")

    frames: list[pd.DataFrame] = []
    for code, currency in series_map.items():
        start = (
            settings.bcb_start_year
            if full
            else _effective_start_year(bq_client, table_fqn, code, settings.bcb_start_year)
        )
        logger.info(
            "BCB currency %s (%s): fetching %d-%d (%s)",
            code,
            currency,
            start,
            settings.bcb_end_year,
            "full" if full else "delta",
        )
        df = fetch_series(code, start, settings.bcb_end_year)
        if df.empty:
            continue
        df = df.rename(columns={"data": "reference_date_str", "valor": "value_str"})
        df["series_code"] = code
        df["currency"] = currency
        frames.append(df[["series_code", "currency", "reference_date_str", "value_str"]])
    if not frames:
        if not full:
            logger.info("BCB currency: no new rows since last ingest.")
            return pd.DataFrame()
        raise RuntimeError("BCB returned no currency data for the configured window.")
    combined = pd.concat(frames, ignore_index=True)
    combined["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
    return combined


def run(settings: Settings, *, full: bool = False) -> str:
    creds = get_credentials(settings)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_bcb_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    destination = f"{dataset_id}.{settings.bq_bronze_bcb_currency_table}"

    df = _extract(settings, bq_client, destination, full=full)
    if df.empty:
        return ""

    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    object_name = (
        f"{settings.gcs_landing_prefix}/bcb/{settings.bq_bronze_bcb_currency_table}/"
        f"run={run_id}/currency_{settings.bcb_start_year}_{settings.bcb_end_year}.parquet"
    )
    upload_dataframe_as_parquet(storage_client, settings.gcs_bucket, object_name, df)

    load_dataframe(
        bq_client,
        df,
        destination,
        BRONZE_SCHEMA,
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=["series_code", "reference_date_str"],
    )
    return destination
