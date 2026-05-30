"""Two-phase Bronze pipeline for MDIC Comex Stat foreign-trade flows.

Phase 1 (``sync_raw``) downloads the verbatim per-(flow, year) CSV, converts it
to Parquet and archives it in the GCS raw zone — but only when the source file
actually changed, decided by comparing the live HTTP ``ETag``/``Last-Modified``
against the archived object's stored provenance. Phase 2 (``bronze_one``) reads
the raw Parquet back, filters to the configured NCMs/chapters, and loads
BigQuery Bronze. See ``PLANS/raw_zone_architecture.md``.

Why two phases: re-filtering (new products/rules) or re-deriving Bronze re-runs
Phase 2 only — reading from GCS, never re-downloading. And the ETag freshness
check catches revisions to *any* year, not just the current one (the old delta
skipped past years permanently once loaded).
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from datetime import UTC

import pandas as pd
from google.cloud import bigquery, storage

from embrapa_commodities.comex import client
from embrapa_commodities.config import Settings, get_credentials
from embrapa_commodities.core import download_raw, land_raw_file, raw_provenance
from embrapa_commodities.gcp.bigquery import ensure_dataset, load_dataframe

logger = logging.getLogger(__name__)

# Segment under raw/comex/<dataset>/ — one raw object per (flow, year).
RAW_DATASET = "comex_flows"

# Bronze layout: flow + the raw source columns (all STRING) + the typed
# ingestion timestamp. Order here is the on-table column order.
BRONZE_STRING_COLUMNS: list[str] = ["flow", *client.SOURCE_COLUMNS]

# Clustering mirrors the columns Silver dedupes / filters on most. BigQuery
# caps clustering at 4 columns, so the full natural key
# (flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM) is trimmed to the four
# most selective for typical product×year×country queries.
CLUSTERING_FIELDS: list[str] = ["flow", "CO_NCM", "CO_ANO", "CO_PAIS"]


def _basename(flow: str, year: int) -> str:
    """Raw object basename for a (flow, year) — e.g. ``EXP_2023``."""
    return f"{client.FILE_PREFIX[flow]}_{year}"


def bronze_schema() -> list[bigquery.SchemaField]:
    """``flow`` + raw STRING columns + typed ``ingestion_timestamp``.

    All source columns are NULLABLE: export rows legitimately lack
    ``VL_FRETE``/``VL_SEGURO``, and a raw feed may carry blank fields elsewhere.
    """
    schema = [bigquery.SchemaField("flow", "STRING", mode="REQUIRED")]
    schema += [
        bigquery.SchemaField(col, "STRING", mode="NULLABLE") for col in client.SOURCE_COLUMNS
    ]
    schema.append(bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"))
    return schema


def all_chunks(settings: Settings) -> list[tuple[str, int]]:
    """Every configured ``(flow, year)``, in flow-then-year order.

    Two-phase ingestion enumerates the full window every run — the per-file
    freshness check (Phase 1) makes re-visiting cheap (a HEAD), so there is no
    Bronze-presence delta to compute up front.
    """
    start, end = settings.comex_start_year, settings.comex_end_year
    return [(flow, year) for flow in settings.comex_flows_list for year in range(start, end + 1)]


def _raw_is_current(stored: dict[str, str] | None, head: dict[str, str]) -> bool:
    """True when the archived raw matches the live source by the first shared
    identifier (ETag > Last-Modified > Content-Length). Missing archive or no
    comparable identifier → not current (re-extract to be safe)."""
    if not stored:
        return False
    for key in ("source_etag", "source_last_modified", "source_content_length"):
        live, archived = head.get(key), stored.get(key)
        if live is not None and archived is not None:
            return live == archived
    return False


def sync_raw(
    settings: Settings,
    flow: str,
    year: int,
    *,
    storage_client: storage.Client,
    force: bool = False,
) -> bool:
    """Phase 1: archive the verbatim ``(flow, year)`` CSV as raw Parquet if changed.

    Returns ``True`` when it (re)extracted, ``False`` when the archived raw was
    already current (download skipped). ``force`` ignores the freshness check.
    """
    basename = _basename(flow, year)
    head = client.head_source(settings.comex_csv_base_url, flow, year)
    if not force:
        stored = raw_provenance(
            storage_client,
            settings=settings,
            source="comex",
            dataset=RAW_DATASET,
            basename=basename,
        )
        if _raw_is_current(stored, head):
            logger.info(
                "Comex %s %d: raw current (source unchanged), skipping download.", flow, year
            )
            return False

    fd, pq_path = tempfile.mkstemp(prefix=f"comex_raw_{basename}_", suffix=".parquet")
    os.close(fd)
    try:
        rows = client.extract_to_parquet(settings.comex_csv_base_url, flow, year, pq_path)
        land_raw_file(
            pq_path,
            settings=settings,
            storage_client=storage_client,
            source="comex",
            dataset=RAW_DATASET,
            basename=basename,
            provenance=head,
            rows=rows,
        )
    finally:
        with contextlib.suppress(OSError):
            os.unlink(pq_path)
    return True


def bronze_one(
    settings: Settings,
    flow: str,
    year: int,
    *,
    storage_client: storage.Client,
    bq_client: bigquery.Client,
    table_fqn: str,
) -> str:
    """Phase 2: filter the raw ``(flow, year)`` Parquet and load BigQuery Bronze.

    Returns the destination, or ``""`` when no configured product matched (no
    empty Bronze append).
    """
    basename = _basename(flow, year)
    raw_bytes = download_raw(
        storage_client, settings=settings, source="comex", dataset=RAW_DATASET, basename=basename
    )
    df = client.filter_products(
        raw_bytes, set(settings.comex_ncm_map), set(settings.comex_chapter_map)
    )
    if df.empty:
        logger.info("Comex %s %d: no configured products in raw, skipping bronze.", flow, year)
        return ""

    # NaN (reindexed import-only columns on export, or blank source fields)
    # must land as SQL NULL, not the literal string "nan".
    df = df.astype(object).where(pd.notna(df), None)
    df.insert(0, "flow", flow)
    df["ingestion_timestamp"] = pd.Timestamp.now(tz=UTC)
    df = df[[*BRONZE_STRING_COLUMNS, "ingestion_timestamp"]]

    load_dataframe(
        bq_client,
        df,
        table_fqn,
        bronze_schema(),
        time_partitioning_field="ingestion_timestamp",
        clustering_fields=CLUSTERING_FIELDS,
    )
    return table_fqn


def has_raw(settings: Settings, flow: str, year: int, *, storage_client: storage.Client) -> bool:
    """Whether a raw object exists for ``(flow, year)`` (used by ``--from-raw``)."""
    return (
        raw_provenance(
            storage_client,
            settings=settings,
            source="comex",
            dataset=RAW_DATASET,
            basename=_basename(flow, year),
        )
        is not None
    )


def ensure_destination(settings: Settings, bq_client: bigquery.Client) -> str:
    """Create the Bronze dataset if needed and return the table FQN."""
    dataset_id = f"{settings.gcp_project_id}.{settings.bq_bronze_comex_dataset}"
    ensure_dataset(bq_client, dataset_id, settings.bq_location)
    return f"{dataset_id}.{settings.bq_bronze_comex_flows_table}"


def run(
    settings: Settings,
    *,
    full: bool = False,
    from_raw: bool = False,
    storage_client: storage.Client | None = None,
    bq_client: bigquery.Client | None = None,
) -> str:
    """Sync raw (Phase 1) then load Bronze (Phase 2). Returns the last destination, or ``""``.

    Default: per (flow, year), re-download only if the source changed, and load
    Bronze for the ones that changed. ``full`` forces a re-download of every
    file. ``from_raw`` skips Phase 1 entirely and rebuilds Bronze from whatever
    raw is already archived (re-filter without touching the source).
    """
    creds = get_credentials(settings)
    bq_client = bq_client or bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    storage_client = storage_client or storage.Client(
        project=settings.gcp_project_id, credentials=creds
    )
    table_fqn = ensure_destination(settings, bq_client)

    last_destination = ""
    for flow, year in all_chunks(settings):
        if from_raw:
            if not has_raw(settings, flow, year, storage_client=storage_client):
                continue
        elif not sync_raw(settings, flow, year, storage_client=storage_client, force=full):
            continue  # raw unchanged → Bronze already current
        destination = bronze_one(
            settings,
            flow,
            year,
            storage_client=storage_client,
            bq_client=bq_client,
            table_fqn=table_fqn,
        )
        if destination:
            last_destination = destination
    return last_destination
