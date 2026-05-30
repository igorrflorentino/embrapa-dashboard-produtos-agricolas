"""Bronze-layer pipeline for IBGE PEVS."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities import observability
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_and_load
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.ibge.client import fetch_sidra_dataframe

logger = logging.getLogger(__name__)


def _bronze_schema(columns: list[str]) -> list[bigquery.SchemaField]:
    """All raw SIDRA columns are STRING; only ingestion_timestamp is typed."""
    schema = [
        bigquery.SchemaField(col, "STRING", mode="NULLABLE")
        for col in columns
        if col != "ingestion_timestamp"
    ]
    schema.append(bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"))
    return schema


def run(
    settings: Settings,
    *,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Extract → land in GCS → load into BigQuery Bronze. Returns destination table id.

    Optional `storage_client` / `bq_client` let callers (e.g. the batch CLI)
    reuse a single client across many chunks instead of re-authenticating per run.
    """
    if settings.ibge_start_year is None:
        raise RuntimeError(
            "IBGE_START_YEAR is empty. Run `embrapa discover ibge-periods "
            f"--table-id {settings.ibge_table_id}` to find the first available year."
        )

    product_codes = settings.product_codes
    logger.info(
        "Ingesting PEVS table=%s classification=%s products=%s years=%d-%d",
        settings.ibge_table_id,
        settings.ibge_classification_id,
        product_codes,
        settings.ibge_start_year,
        settings.ibge_end_year,
    )

    started = time.monotonic()
    df = fetch_sidra_dataframe(
        table_id=settings.ibge_table_id,
        start_year=settings.ibge_start_year,
        end_year=settings.ibge_end_year,
        classification=settings.ibge_classification_id,
        products=product_codes,
        geo_level="n6",
    )

    if df.empty:
        # SIDRA had nothing to give us — almost always because IBGE_END_YEAR
        # is set to a year that hasn't been published yet. Skip upload/load
        # so Bronze doesn't accumulate empty Parquet files, and tell the user.
        observability.emit(
            "ingest_empty",
            pipeline="ibge",
            start_year=settings.ibge_start_year,
            end_year=settings.ibge_end_year,
            duration_s=round(time.monotonic() - started, 2),
        )
        logger.warning(
            "IBGE ingest skipped: SIDRA returned no rows for %d-%d. "
            "Lower IBGE_END_YEAR in .env to the latest published year.",
            settings.ibge_start_year,
            settings.ibge_end_year,
        )
        return ""

    # One timestamp for both the column and the GCS run_id — they should
    # describe the same instant so reconciliation is unambiguous.
    now = datetime.now(UTC)
    df = df.astype(str)
    df["ingestion_timestamp"] = pd.Timestamp(now)

    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=get_credentials(settings)
    )
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id,
        location=settings.bq_location,
        credentials=get_credentials(settings),
    )
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_ibge_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)

    destination = land_and_load(
        df,
        settings=settings,
        storage_client=storage_client,
        bq_client=bq_client,
        source="ibge",
        table=settings.bq_bronze_ibge_table,
        object_basename=(
            f"products_{'_'.join(product_codes)}_"
            f"{settings.ibge_start_year}_{settings.ibge_end_year}"
        ),
        destination=f"{dataset_id}.{settings.bq_bronze_ibge_table}",
        schema=_bronze_schema(list(df.columns)),
        # Match Silver's dedupe partition keys so qualify-row_number scans
        # only relevant blocks instead of the full Bronze history.
        clustering_fields=["municipio_codigo", "ano", "variavel_codigo"],
        # Share the column timestamp's instant with the GCS run= path.
        run_id=now.strftime("%Y%m%dT%H%M%SZ"),
    )
    observability.emit(
        "ingest_loaded",
        pipeline="ibge",
        rows=len(df),
        duration_s=round(time.monotonic() - started, 2),
        start_year=settings.ibge_start_year,
        end_year=settings.ibge_end_year,
        destination=destination,
    )
    return destination
