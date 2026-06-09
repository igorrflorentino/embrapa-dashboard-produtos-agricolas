"""Raw-zone primitive: verbatim source extracts archived in GCS before Bronze.

Two-phase ingestion (see ``PLANS/raw_zone_architecture.md``): every source first
lands its *verbatim* extract here — ``raw/<source>/<dataset>/<basename>.parquet``
with provenance metadata — then a Bronze step reads it back, filters/shapes, and
loads BigQuery. Decoupling fetch from load means re-filtering or re-deriving
Bronze never re-hits the source: only a genuine source revision (detected via
the stored provenance, e.g. an HTTP ETag) triggers a re-fetch.

What lives here: the source-agnostic GCS read/write of the raw archive plus its
provenance metadata. What does NOT: the per-source extract (fetch), the filter,
the BQ load (``gcp/bigquery.load_dataframe``), and the freshness *decision*
(source-specific — ETag for COMEX, max-date for BCB).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from io import BytesIO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

from embrapa_commodities.config import Settings
from embrapa_commodities.gcp.storage import ensure_bucket

logger = logging.getLogger(__name__)

# Wall-clock ceiling for a single GCS object op (upload / download / metadata).
# google-cloud-storage defaults to 60s; raw Parquet objects are small but a
# stalled connection on an unattended Cloud Run ingest should still time out
# rather than hang the job forever. 300s leaves slack for the largest raw blobs.
GCS_TIMEOUT_S: float = 300.0


def raw_object_name(settings: Settings, source: str, dataset: str, basename: str) -> str:
    """Canonical GCS object path for a raw extract.

    ``raw/<source>/<dataset>/<basename>.parquet`` — one object per logical
    extract unit (e.g. COMEX ``(flow, year)``, a BCB series window, an IBGE
    chunk). Deterministic so a re-extract overwrites the same object (GCS
    Object Versioning keeps the prior version for recovery).
    """
    return f"{settings.gcs_raw_prefix}/{source}/{dataset}/{basename}.parquet"


def land_raw(
    df: pd.DataFrame,
    *,
    settings: Settings,
    storage_client: storage.Client,
    source: str,
    dataset: str,
    basename: str,
    provenance: dict[str, str] | None = None,
) -> str:
    """Phase 1: archive a verbatim extract as Parquet in the raw zone.

    ``provenance`` is written as GCS custom object metadata (all values coerced
    to ``str``); a ``fetched_at`` UTC stamp and ``rows`` count are always added.
    Returns the ``gs://`` URI.
    """
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    object_name = raw_object_name(settings, source, dataset, basename)

    buffer = BytesIO()
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, buffer, compression="snappy")
    buffer.seek(0)

    blob = storage_client.bucket(settings.gcs_bucket).blob(object_name)
    blob.metadata = _raw_metadata(provenance, source, len(df))
    blob.upload_from_file(buffer, content_type="application/octet-stream", timeout=GCS_TIMEOUT_S)
    uri = f"gs://{settings.gcs_bucket}/{object_name}"
    logger.info("Raw-landed %d rows → %s", len(df), uri)
    return uri


def _raw_metadata(
    provenance: dict[str, str] | None, source: str, rows: int | None
) -> dict[str, str]:
    metadata = {str(k): str(v) for k, v in (provenance or {}).items()}
    metadata.setdefault("source", source)
    metadata["fetched_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if rows is not None:
        metadata["rows"] = str(rows)
    return metadata


def land_raw_file(
    local_path: str,
    *,
    settings: Settings,
    storage_client: storage.Client,
    source: str,
    dataset: str,
    basename: str,
    provenance: dict[str, str] | None = None,
    rows: int | None = None,
) -> str:
    """Phase 1 variant: upload an already-written Parquet *file* to the raw zone.

    For sources whose extract is too large to hold in memory as a DataFrame
    (COMEX streams CSV→Parquet to a temp file in chunks). ``rows`` is optional
    since the caller may not have a cheap count; pass it when known.
    """
    ensure_bucket(storage_client, settings.gcs_bucket, settings.bq_location)
    object_name = raw_object_name(settings, source, dataset, basename)
    blob = storage_client.bucket(settings.gcs_bucket).blob(object_name)
    blob.metadata = _raw_metadata(provenance, source, rows)
    blob.upload_from_filename(
        local_path, content_type="application/octet-stream", timeout=GCS_TIMEOUT_S
    )
    uri = f"gs://{settings.gcs_bucket}/{object_name}"
    logger.info("Raw-landed file → %s", uri)
    return uri


def read_raw(
    storage_client: storage.Client,
    *,
    settings: Settings,
    source: str,
    dataset: str,
    basename: str,
) -> pd.DataFrame:
    """Phase 2: read a raw extract back from GCS into a DataFrame (small extracts)."""
    return pd.read_parquet(
        BytesIO(
            download_raw(
                storage_client, settings=settings, source=source, dataset=dataset, basename=basename
            )
        )
    )


def download_raw(
    storage_client: storage.Client,
    *,
    settings: Settings,
    source: str,
    dataset: str,
    basename: str,
) -> bytes:
    """Phase 2: raw Parquet bytes. For large extracts, feed into
    ``pyarrow.parquet.ParquetFile(BytesIO(...)).iter_batches()`` so the filter
    stays memory-bounded (the compressed Parquet download is small)."""
    object_name = raw_object_name(settings, source, dataset, basename)
    blob = storage_client.bucket(settings.gcs_bucket).blob(object_name)
    return blob.download_as_bytes(timeout=GCS_TIMEOUT_S)


def list_raw(
    storage_client: storage.Client,
    *,
    settings: Settings,
    source: str,
    dataset: str,
) -> list[str]:
    """Every archived basename under ``raw/<source>/<dataset>/`` (sorted).

    For sources that append a run-stamped raw object per extract (BCB), this is
    how ``--from-raw`` enumerates the full trail to rebuild Bronze from.
    """
    prefix = f"{settings.gcs_raw_prefix}/{source}/{dataset}/"
    suffix = ".parquet"
    basenames = [
        blob.name[len(prefix) : -len(suffix)]
        for blob in storage_client.list_blobs(settings.gcs_bucket, prefix=prefix)
        if blob.name.endswith(suffix)
    ]
    return sorted(basenames)


def raw_provenance(
    storage_client: storage.Client,
    *,
    settings: Settings,
    source: str,
    dataset: str,
    basename: str,
) -> dict[str, str] | None:
    """Return the provenance metadata of an archived raw extract, or ``None``.

    ``None`` means the object does not exist yet (nothing archived) — a
    source-specific freshness check treats that as "must extract".
    """
    object_name = raw_object_name(settings, source, dataset, basename)
    blob = storage_client.bucket(settings.gcs_bucket).get_blob(object_name, timeout=GCS_TIMEOUT_S)
    if blob is None:
        return None
    return blob.metadata or {}


# Custom-metadata key stamped on a raw object once Bronze has been loaded from it.
BRONZE_LOADED_KEY = "bronze_loaded_at"


def mark_raw_bronze_loaded(
    storage_client: storage.Client,
    *,
    settings: Settings,
    source: str,
    dataset: str,
    basename: str,
) -> None:
    """Stamp an archived raw object as having been loaded into Bronze (Phase 2).

    This is the source of truth that closes the gap where ``raw present`` was
    *assumed* to mean ``Bronze loaded``: a prior run could archive the raw (Phase
    1) then abort before the load, and a delta re-run would then skip Phase 2 on
    the unchanged raw, leaving that partition permanently absent from Bronze.
    With the marker, a skip is only taken when the raw is both current AND already
    loaded (see ``raw_bronze_loaded``). A re-extract rewrites the object's
    metadata wholesale, which clears this marker, so it always reflects whether
    *the current raw version* has been loaded.
    """
    object_name = raw_object_name(settings, source, dataset, basename)
    blob = storage_client.bucket(settings.gcs_bucket).get_blob(object_name, timeout=GCS_TIMEOUT_S)
    if blob is None:  # nothing archived (e.g. an empty fetch landed no object)
        return
    metadata = dict(blob.metadata or {})
    metadata[BRONZE_LOADED_KEY] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    blob.metadata = metadata
    blob.patch(timeout=GCS_TIMEOUT_S)


def raw_bronze_loaded(stored: dict[str, str] | None) -> bool:
    """Whether raw provenance shows Bronze was loaded from this raw version."""
    return bool(stored and stored.get(BRONZE_LOADED_KEY))
