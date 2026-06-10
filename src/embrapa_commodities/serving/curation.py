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

# Free-text length caps. processing_stage / note are intentionally NOT allowlisted:
# the research curation flow lets a researcher coin arbitrary stage labels and
# notes (open vocabulary by design — an allowlist would break that UX). These caps
# are a cheap guard against an absurdly large value (a runaway paste / malformed
# client) bloating the immutable audit row, not a content restriction.
MAX_STAGE_LEN = 200
MAX_NOTE_LEN = 2000

# Explicit schema — autodetect is never used (it drifts silently across runs).
CURATION_LOG_SCHEMA = [
    bigquery.SchemaField("commodity_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("processing_stage", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("note", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("edited_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("edited_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("change_id", "STRING", mode="REQUIRED"),
]

# The per-CODE industrialization log — one grain finer than the commodity log.
CODE_INDUSTRIALIZATION_LOG_SCHEMA = [
    bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("code", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("industrialization_level", "STRING", mode="REQUIRED"),
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


def _validate_edit_text(commodity_id: str, processing_stage: str, note: str | None) -> None:
    """Validate edit inputs: required fields present and free text within size caps.

    Stages/notes are open-vocabulary by design (no allowlist); these are only
    sanity bounds so a runaway value can't bloat the immutable audit row.
    """
    if not commodity_id or not processing_stage:
        raise ValueError("commodity_id and processing_stage are required.")
    if len(processing_stage) > MAX_STAGE_LEN:
        raise ValueError(f"processing_stage exceeds {MAX_STAGE_LEN} chars.")
    if note is not None and len(note) > MAX_NOTE_LEN:
        raise ValueError(f"note exceeds {MAX_NOTE_LEN} chars.")


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
    as written (for the UI to confirm). Raises on empty inputs, an over-length
    stage/note, or a missing author with no dev fallback.
    """
    cfg = settings or get_settings()
    commodity_id = (commodity_id or "").strip()
    processing_stage = (processing_stage or "").strip()
    note = note.strip() if note else note
    _validate_edit_text(commodity_id, processing_stage, note)

    # When iap_audience is set (production), the author comes from the verified
    # IAP JWT — the plaintext header is spoofable and must not decide edited_by.
    # When unset (local dev), fall back to the plaintext header + dev author.
    edited_by = author_email_from_headers(
        headers,
        dev_fallback=cfg.curation_dev_author,
        audience=cfg.iap_audience,
    )
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
    # INTENTIONAL: log the researcher's email at INFO on every save. This is the
    # operational side of the audit trail (who reclassified what) — deliberate
    # attribution of a human action, the same identity already persisted in the
    # immutable edited_by column. Keep it; it is not incidental PII leakage.
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
        # flask-caching's delete_memoized bumps a per-function VERSION sentinel
        # rather than deleting each cached entry: the next read computes a fresh
        # key and misses, so subsequent reads see new data immediately. The old
        # entries are orphaned (unreferenced) and simply expire at their TTL —
        # we accept that small, bounded residue (consistency restored at once;
        # eviction within <= TTL) instead of re-architecting flask-caching.
        cache.delete_memoized(gateway.fetch_current_classifications)
    except Exception as exc:  # pragma: no cover - cache unbound / backend down
        logger.warning("Could not invalidate classification cache: %s", exc)


# ── Per-CODE industrialization log (the finer-grained companion) ──────────────
def ensure_code_industrialization_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the per-code industrialization log dataset + table if missing.

    Same house auto-create pattern as :func:`ensure_curation_log_table`, clustered
    by (source, code) so the SCD2 window scans one code's edits cheaply. Idempotent.
    """
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(
        cfg, "bq_research_inputs_dataset", cfg.bq_code_industrialization_log_table
    )
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=CODE_INDUSTRIALIZATION_LOG_SCHEMA)
    table.clustering_fields = ["source", "code"]
    bq.create_table(table, exists_ok=True)
    logger.info("Code-industrialization log ready at %s", table_fqn)
    return table_fqn


def _validate_code_edit(source: str, code: str, level: str, note: str | None) -> None:
    """Validate a per-code edit: required keys present and free text within caps.

    ``industrialization_level`` is open-vocabulary like ``processing_stage`` (the
    UI offers bruta/processada/misturado, but an allowlist would break a future
    finer scheme); the cap is only a sanity bound on the immutable audit row.
    """
    if not source or not code or not level:
        raise ValueError("source, code and industrialization_level are required.")
    if len(level) > MAX_STAGE_LEN:
        raise ValueError(f"industrialization_level exceeds {MAX_STAGE_LEN} chars.")
    if note is not None and len(note) > MAX_NOTE_LEN:
        raise ValueError(f"note exceeds {MAX_NOTE_LEN} chars.")


def record_code_industrialization(
    source: str,
    code: str,
    industrialization_level: str,
    headers: Mapping[str, str],
    *,
    note: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Append one per-code industrialization edit and invalidate its cache.

    The per-code companion to :func:`record_processing_stage`: same IAP author
    capture, parameterized DML, and read-after-write consistency, keyed by
    (source, code) → industrialization_level. Returns the row as written.
    """
    cfg = settings or get_settings()
    source = (source or "").strip()
    code = (code or "").strip()
    industrialization_level = (industrialization_level or "").strip()
    note = note.strip() if note else note
    _validate_code_edit(source, code, industrialization_level, note)

    edited_by = author_email_from_headers(
        headers,
        dev_fallback=cfg.curation_dev_author,
        audience=cfg.iap_audience,
    )
    change_id = uuid.uuid4().hex
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(
        cfg, "bq_research_inputs_dataset", cfg.bq_code_industrialization_log_table
    )

    sql = f"""
        insert into `{table_fqn}`
            (source, code, industrialization_level, note, edited_by, edited_at, change_id)
        values
            (@source, @code, @level, @note, @edited_by, current_timestamp(), @change_id)
    """
    params = [
        bigquery.ScalarQueryParameter("source", "STRING", source),
        bigquery.ScalarQueryParameter("code", "STRING", code),
        bigquery.ScalarQueryParameter("level", "STRING", industrialization_level),
        bigquery.ScalarQueryParameter("note", "STRING", note),
        bigquery.ScalarQueryParameter("edited_by", "STRING", edited_by),
        bigquery.ScalarQueryParameter("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    logger.info(
        "Curation(code): %s:%s -> %s by %s", source, code, industrialization_level, edited_by
    )

    if invalidate_cache:
        invalidate_code_industrialization_cache()

    return {
        "source": source,
        "code": code,
        "industrialization_level": industrialization_level,
        "note": note,
        "edited_by": edited_by,
        "change_id": change_id,
    }


def invalidate_code_industrialization_cache() -> None:
    """Drop the cached per-code classification read (best-effort), same contract
    as :func:`invalidate_classification_cache`."""
    try:
        cache.delete_memoized(gateway.fetch_current_code_industrialization)
    except Exception as exc:  # pragma: no cover - cache unbound / backend down
        logger.warning("Could not invalidate code-industrialization cache: %s", exc)
