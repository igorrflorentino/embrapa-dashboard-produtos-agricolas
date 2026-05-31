"""Two-phase Bronze pipeline for IBGE PEVS.

Phase 1 (``extract_raw``) fetches the SIDRA response (already filtered by the
API query — table, classification, products, year window) and archives it
verbatim to the GCS raw zone. Phase 2 (``bronze_from_raw``) reads it back,
stamps ``ingestion_timestamp`` and loads BigQuery Bronze. See
``PLANS/raw_zone_architecture.md``.

SIDRA is queried fresh each run (a POST with no ETag), so Phase 1 always
re-extracts and overwrites the raw object for the configured window; the
``--from-raw`` path rebuilds Bronze from that archive without re-querying SIDRA.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities import observability
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import land_raw, raw_provenance, read_raw
from embrapa_commodities.gcp.bigquery import ensure_dataset, load_dataframe
from embrapa_commodities.ibge.client import fetch_sidra_dataframe

logger = logging.getLogger(__name__)

# Segment under raw/ibge/<dataset>/ — one raw object per configured window.
RAW_DATASET = "pevs"

CLUSTERING_FIELDS = ["municipio_codigo", "ano", "variavel_codigo"]


def _bronze_schema(columns: list[str]) -> list[bigquery.SchemaField]:
    """All raw SIDRA columns are STRING; only ingestion_timestamp is typed."""
    schema = [
        bigquery.SchemaField(col, "STRING", mode="NULLABLE")
        for col in columns
        if col != "ingestion_timestamp"
    ]
    schema.append(bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"))
    return schema


def _basename(settings: Settings) -> str:
    """Raw object basename encoding the products + window — same identity as the
    old landing object, so re-running the same config overwrites one object."""
    return (
        f"products_{'_'.join(settings.product_codes)}_"
        f"{settings.ibge_start_year}_{settings.ibge_end_year}"
    )


def extract_raw(settings: Settings, *, storage_client: storage.Client) -> str | None:
    """Phase 1: fetch SIDRA and archive the verbatim response. Returns the raw
    basename, or ``None`` when SIDRA had no rows (nothing archived)."""
    if settings.ibge_start_year is None:
        raise RuntimeError(
            "IBGE_START_YEAR is empty. Run `embrapa discover ibge-periods "
            f"--table-id {settings.ibge_table_id}` to find the first available year."
        )
    product_codes = settings.product_codes
    started = time.monotonic()
    logger.info(
        "Ingesting PEVS table=%s classification=%s products=%s years=%d-%d",
        settings.ibge_table_id,
        settings.ibge_classification_id,
        product_codes,
        settings.ibge_start_year,
        settings.ibge_end_year,
    )
    df = fetch_sidra_dataframe(
        table_id=settings.ibge_table_id,
        start_year=settings.ibge_start_year,
        end_year=settings.ibge_end_year,
        classification=settings.ibge_classification_id,
        products=product_codes,
        geo_level="n6",
    )
    if df.empty:
        # SIDRA had nothing — almost always IBGE_END_YEAR set past the latest
        # published year. Skip so the raw zone / Bronze don't accumulate empties.
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
        return None

    basename = _basename(settings)
    land_raw(
        df.astype(str),
        settings=settings,
        storage_client=storage_client,
        source="ibge",
        dataset=RAW_DATASET,
        basename=basename,
        provenance={
            "source": "ibge-sidra",
            "table_id": settings.ibge_table_id,
            "classification": settings.ibge_classification_id,
            "products": ",".join(product_codes),
            "start_year": str(settings.ibge_start_year),
            "end_year": str(settings.ibge_end_year),
        },
    )
    return basename


def bronze_from_raw(
    settings: Settings,
    basename: str,
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
) -> str:
    """Phase 2: read the raw SIDRA archive, stamp ingestion_timestamp, load Bronze."""
    df = read_raw(
        storage_client, settings=settings, source="ibge", dataset=RAW_DATASET, basename=basename
    )
    df = df.astype(str)
    df["ingestion_timestamp"] = pd.Timestamp.now(tz="UTC")

    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_ibge_dataset}"
    destination = f"{dataset_id}.{settings.bq_bronze_ibge_table}"
    load_dataframe(
        bq_client,
        df,
        destination,
        _bronze_schema(list(df.columns)),
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=CLUSTERING_FIELDS,
    )
    observability.emit("ingest_loaded", pipeline="ibge", rows=len(df), destination=destination)
    return destination


def run(
    settings: Settings,
    *,
    from_raw: bool = False,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Extract→raw (Phase 1) then raw→Bronze (Phase 2). Returns destination, or ``""``.

    ``from_raw`` rebuilds Bronze from the archived raw without re-querying SIDRA.
    Optional clients let the batch CLI reuse one client across chunks.
    """
    creds = get_credentials(settings)
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_ibge_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)

    if from_raw:
        basename = _basename(settings)
        if (
            raw_provenance(
                storage_client,
                settings=settings,
                source="ibge",
                dataset=RAW_DATASET,
                basename=basename,
            )
            is None
        ):
            logger.warning("IBGE --from-raw: no raw archived for %s.", basename)
            return ""
    else:
        basename = extract_raw(settings, storage_client=storage_client)
        if basename is None:
            return ""

    return bronze_from_raw(settings, basename, storage_client=storage_client, bq_client=bq_client)
