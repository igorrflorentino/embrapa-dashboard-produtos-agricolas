"""Curadoria lifecycle — orphan → Descontinuado (NON-destructive).

When a commodity is removed from the catalog (a tombstone, active=false) its already
ingested Gold data does not vanish — it lingers, "órfão". This module detects that
transition and appends a ``descontinuado`` lifecycle event WITH a deletion warning —
but it NEVER deletes anything. The actual purge is a separate, human-gated, backup-first
operator action (the lead's decision #2): auto-detect + auto-mark + warn is automatic;
the delete waits for a person.

Detection is precise (see ``gateway.fetch_orphan_commodities``): only a REMOVAL that
leaves Gold data behind counts — not every uncataloged Gold code (the catalog is a
cross-source bridge, not a full registry; that diff would false-flag legitimate products).

Append-only log ``research_inputs.catalog_lifecycle_log`` (latest-wins per
(element_kind, banco, code)); the auto-mark is idempotent (a deterministic change_id per
element), so re-running it is a no-op. The author is a reserved SYSTEM identity, so the
audit row is honest about being machine-generated.
"""

from __future__ import annotations

import logging

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache
from embrapa_commodities.serving.research_inputs import _bq_client, _change_id_seen

logger = logging.getLogger(__name__)

# The machine identity that marks orphans (never an IAP person — auto-mark has no request).
ORPHAN_DETECTOR_AUTHOR = "system:orphan-detector"
# The warning every Descontinuado element carries. The purge is human-gated, backup-first.
PURGE_WARNING = (
    "Descontinuada: será removida do Gold por um operador (com backup), nunca automaticamente."
)

CATALOG_LIFECYCLE_LOG_SCHEMA = [
    bigquery.SchemaField("element_kind", "STRING", mode="REQUIRED"),  # 'commodity' | 'banco'
    bigquery.SchemaField("banco", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("code", "STRING", mode="NULLABLE"),  # codigo_commodity; NULL for a banco
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),  # 'descontinuado' | 'purged'
    bigquery.SchemaField("reason", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("scheduled_purge_note", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("edited_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("edited_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("change_id", "STRING", mode="REQUIRED"),
]


def _lifecycle_log_ref(cfg: Settings) -> str:
    return sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_catalog_lifecycle_log_table)


def ensure_catalog_lifecycle_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the append-only lifecycle log if missing (clustered by element). Idempotent."""
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = _lifecycle_log_ref(cfg)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=CATALOG_LIFECYCLE_LOG_SCHEMA)
    table.clustering_fields = ["element_kind", "banco"]
    bq.create_table(table, exists_ok=True)
    logger.info("Catalog-lifecycle log ready at %s", table_fqn)
    return table_fqn


def _insert_lifecycle_event(
    bq, table_fqn, *, element_kind, banco, code, status, reason, purge_note, edited_by, change_id
) -> None:
    """Append one lifecycle event (parameterized DML, server-side timestamp)."""
    sql = f"""
        insert into `{table_fqn}`
            (element_kind, banco, code, status, reason, scheduled_purge_note,
             edited_by, edited_at, change_id)
        values
            (@element_kind, @banco, @code, @status, @reason, @purge_note,
             @edited_by, current_timestamp(), @change_id)
    """
    p = bigquery.ScalarQueryParameter
    params = [
        p("element_kind", "STRING", element_kind),
        p("banco", "STRING", banco),
        p("code", "STRING", code),
        p("status", "STRING", status),
        p("reason", "STRING", reason),
        p("purge_note", "STRING", purge_note),
        p("edited_by", "STRING", edited_by),
        p("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def _current_status(settings: Settings) -> dict:
    """{(element_kind, banco, code): status} from the lifecycle log; {} when absent."""
    try:
        df = gateway.fetch_lifecycle_status()
    except NotFound:
        return {}
    if df is None or df.empty:
        return {}
    return {
        (r.element_kind, r.banco, None if r.code is None else str(r.code)): r.status
        for r in df.itertuples()
    }


def auto_mark_orphans(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> dict:
    """Detect orphan commodities and append a ``descontinuado`` event for any not already
    marked (the automatic half of the lifecycle). Idempotent; NON-destructive. Returns
    ``{detected, newly_marked, already_marked}``."""
    cfg = settings or get_settings()
    try:
        orphans = gateway.fetch_orphan_commodities()
    except NotFound:
        return {"detected": 0, "newly_marked": 0, "already_marked": 0}
    if orphans is None or orphans.empty:
        return {"detected": 0, "newly_marked": 0, "already_marked": 0}

    already = _current_status(cfg)
    bq = client or _bq_client(cfg)
    table_fqn = _lifecycle_log_ref(cfg)
    ensure_catalog_lifecycle_log_table(cfg, bq)

    newly = 0
    for o in orphans.itertuples():
        code = str(o.codigo_commodity)
        banco = o.banco
        if already.get(("commodity", banco, code)) in ("descontinuado", "purged"):
            continue
        change_id = f"descontinuado:commodity:{banco}:{code}"
        if _change_id_seen(bq, table_fqn, change_id):
            continue
        reason = (
            f"Removida do cadastro; dados em Gold pendentes "
            f"(agrupamento {getattr(o, 'agrupamento', None) or '—'})."
        )
        _insert_lifecycle_event(
            bq,
            table_fqn,
            element_kind="commodity",
            banco=banco,
            code=code,
            status="descontinuado",
            reason=reason,
            purge_note=PURGE_WARNING,
            edited_by=ORPHAN_DETECTOR_AUTHOR,
            change_id=change_id,
        )
        newly += 1
        logger.info("Lifecycle: %s:%s -> descontinuado (orphan)", banco, code)

    if newly:
        invalidate_lifecycle_cache()
    return {
        "detected": len(orphans),
        "newly_marked": newly,
        "already_marked": len(orphans) - newly,
    }


def invalidate_lifecycle_cache() -> None:
    """Drop the cached lifecycle-status + orphan reads (best-effort)."""
    for fn in (gateway.fetch_lifecycle_status, gateway.fetch_orphan_commodities):
        try:
            cache.delete_memoized(fn)
        except Exception as exc:  # pragma: no cover - cache unbound / backend down
            logger.warning("Could not invalidate lifecycle cache: %s", exc)
