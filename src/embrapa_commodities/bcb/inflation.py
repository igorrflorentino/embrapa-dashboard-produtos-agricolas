"""Bronze pipeline for BCB inflation indices — codes configurable via .env."""

from __future__ import annotations

import logging
from datetime import UTC

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.bcb.client import fetch_series
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_and_load
from embrapa_commodities.gcp.bigquery import ensure_dataset, latest_reference_date

logger = logging.getLogger(__name__)

# Overlap (in months) re-fetched on each delta run to absorb BCB revisions
# without missing them. BCB occasionally re-publishes the trailing few months
# of IPCA (preliminary → final reading).
DELTA_OVERLAP_MONTHS = 12

BRONZE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("series_code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("series_name", "STRING", mode="REQUIRED"),
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
    """Pick a start year: max(configured, last_loaded - 1y) so we re-fetch
    only the recent overlap window, not the whole 1980-now history."""
    last = latest_reference_date(bq_client, table_fqn, code)
    if last is None:
        return configured_start
    # 12-month overlap absorbs BCB revisions of preliminary readings.
    delta_start = last.year - (DELTA_OVERLAP_MONTHS // 12)
    return max(configured_start, delta_start)


def _extract(
    settings: Settings,
    bq_client: bigquery.Client,
    table_fqn: str,
    *,
    full: bool,
) -> pd.DataFrame:
    series_map = settings.inflation_series_map
    if not series_map:
        raise RuntimeError("BCB_INFLATION_SERIES is empty.")

    frames: list[pd.DataFrame] = []
    for code, name in series_map.items():
        start = (
            settings.bcb_start_year
            if full
            else _effective_start_year(bq_client, table_fqn, code, settings.bcb_start_year)
        )
        logger.info(
            "BCB inflation %s: fetching %d-%d (%s)",
            code,
            start,
            settings.bcb_end_year,
            "full" if full else "delta",
        )
        df = fetch_series(code, start, settings.bcb_end_year)
        if df.empty:
            continue
        df = df.rename(columns={"data": "reference_date_str", "valor": "value_str"})
        df["series_code"] = code
        df["series_name"] = name
        frames.append(df[["series_code", "series_name", "reference_date_str", "value_str"]])
    if not frames:
        # In delta mode, an empty fetch just means "nothing new" — not an error.
        if not full:
            logger.info("BCB inflation: no new rows since last ingest.")
            return pd.DataFrame()
        raise RuntimeError("BCB returned no inflation data for the configured window.")
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
    destination = f"{dataset_id}.{settings.bq_bronze_bcb_inflation_table}"

    df = _extract(settings, bq_client, destination, full=full)
    if df.empty:
        return ""

    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    return land_and_load(
        df,
        settings=settings,
        storage_client=storage_client,
        bq_client=bq_client,
        source="bcb",
        table=settings.bq_bronze_bcb_inflation_table,
        object_basename=f"inflation_{settings.bcb_start_year}_{settings.bcb_end_year}",
        destination=destination,
        schema=BRONZE_SCHEMA,
        clustering_fields=["series_code", "reference_date_str"],
    )
