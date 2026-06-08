"""Append-only curation writer — the backend of the dashboard's "Save" button.

When a researcher reclassifies a commodity and clicks Save, this module appends
ONE immutable row to ``research_inputs.commodity_processing_stage_log``. The Gold
tables are never touched; the Type-2 history (valid_from / valid_to / is_current)
is derived downstream by the ``dim_commodity_scd2`` dbt view.

Two side effects matter:
  1. The author is taken from the IAP-verified header (``edited_by``), never from
     the dashboard's service account — every edit is attributable to a person.
  2. After the insert, the live-classification cache is invalidated so the next
     read reflects the new stage immediately (the marts are untouched, so their
     caches are left alone).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_credentials, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache
from embrapa_commodities.serving.iap import author_email_from_headers

logger = logging.getLogger(__name__)

# Explicit schema — autodetect is never used (it drifts silently across runs).
CURATION_LOG_SCHEMA = [
    bigquery.SchemaField("commodity_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("processing_stage", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("note", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("edited_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("edited_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("change_id", "STRING", mode="REQUIRED"),
]


def _bq_client(settings: Settings) -> bigquery.Client:
    return bigquery.Client(
        project=settings.gcp_project_id,
        location=settings.bq_location,
        credentials=get_credentials(settings),
    )


def ensure_curation_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the append-only log dataset + table if missing; return its FQN.

    Follows the house auto-create pattern (like the Bronze ensure_* helpers) so a
    fresh project needs no manual DDL. Idempotent.
    """
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_curation_log_table)

    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=CURATION_LOG_SCHEMA)
    # Append-only audit log — cluster by commodity_id so the SCD2 window scans a
    # single commodity's edits cheaply.
    table.clustering_fields = ["commodity_id"]
    bq.create_table(table, exists_ok=True)
    logger.info("Curation log ready at %s", table_fqn)
    return table_fqn


def record_processing_stage(
    commodity_id: str,
    processing_stage: str,
    headers: Mapping[str, str],
    *,
    note: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Append one classification edit and invalidate the classification cache.

    ``headers`` is the inbound request's headers (``flask.request.headers`` in a
    Dash callback); the author email is read from the IAP header. Returns the row
    as written (for the UI to confirm). Raises on empty inputs or a missing
    author with no dev fallback.
    """
    cfg = settings or get_settings()
    commodity_id = (commodity_id or "").strip()
    processing_stage = (processing_stage or "").strip()
    if not commodity_id or not processing_stage:
        raise ValueError("commodity_id and processing_stage are required.")

    edited_by = author_email_from_headers(headers, dev_fallback=cfg.curation_dev_author)
    change_id = uuid.uuid4().hex
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_curation_log_table)

    # Parameterized DML INSERT: immediately consistent (read-after-write for the
    # SCD2 view) and injection-safe. edited_at is stamped server-side.
    sql = f"""
        insert into `{table_fqn}`
            (commodity_id, processing_stage, note, edited_by, edited_at, change_id)
        values
            (@commodity_id, @processing_stage, @note, @edited_by, current_timestamp(), @change_id)
    """
    params = [
        bigquery.ScalarQueryParameter("commodity_id", "STRING", commodity_id),
        bigquery.ScalarQueryParameter("processing_stage", "STRING", processing_stage),
        bigquery.ScalarQueryParameter("note", "STRING", note),
        bigquery.ScalarQueryParameter("edited_by", "STRING", edited_by),
        bigquery.ScalarQueryParameter("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    logger.info("Curation: %s -> %s by %s", commodity_id, processing_stage, edited_by)

    if invalidate_cache:
        invalidate_classification_cache()

    return {
        "commodity_id": commodity_id,
        "processing_stage": processing_stage,
        "note": note,
        "edited_by": edited_by,
        "change_id": change_id,
    }


def invalidate_classification_cache() -> None:
    """Drop the cached live-classification read so the next query is fresh.

    Best-effort: a no-op if the cache is not bound to an app (e.g. a CLI-driven
    write outside the Dash server). With the per-instance ``SimpleCache`` this
    clears only the current process — making the edit instant on the writing
    instance; other instances converge within the short classification TTL
    (``CACHE_CLASSIFICATION_TIMEOUT``). That bound is what lets multi-instance
    Cloud Run run on ``SimpleCache`` without ``RedisCache`` (see ``serving.cache``).
    """
    try:
        cache.delete_memoized(gateway.fetch_current_classifications)
    except Exception as exc:  # pragma: no cover - cache unbound / backend down
        logger.warning("Could not invalidate classification cache: %s", exc)
