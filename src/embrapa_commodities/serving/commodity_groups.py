"""Commodity groups (agrupamentos) — the first-class registry of commodity concepts.

A "group" (agrupamento) is the cross-source commodity concept that unifies raw codes
across bancos (e.g. "Madeira", "Castanha"). Historically a group was DERIVED — the
distinct set of ``agrupamento`` names carried on catalog entries — so it had no
independent lifecycle: no empty groups, no rename, no delete. This module promotes
groups to a FIRST-CLASS entity with their own append-only registry, keyed by
``group_id`` (== a catalog entry's ``commodity_id``): create (incl. EMPTY groups),
rename and delete (blocked while the group still has active members).

Reuses the shared append-log primitives in ``serving/research_inputs.py`` (IAP author
capture + latest-wins current state + optional change_id idempotency), exactly like
``serving/curation.py``. A RENAME re-stamps the denormalized ``agrupamento`` name on
the group's member catalog entries (so ``dim_commodity_catalog`` and the crosswalk,
which read the entry's ``agrupamento``, need NO schema change). A DELETE is a tombstone
and is REJECTED while the group has active members — the researcher reassigns/removes
them first (never a silent cascade).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.serving import curation, gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache
from embrapa_commodities.serving.iap import author_email_from_headers
from embrapa_commodities.serving.research_inputs import (
    MAX_NOTE_LEN,
    _bq_client,
    _change_id_seen,
    _resolve_change_id,
)

logger = logging.getLogger(__name__)

# Append-only groups registry. Explicit schema (autodetect drifts silently).
COMMODITY_GROUP_LOG_SCHEMA = [
    bigquery.SchemaField("group_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("group_name", "STRING", mode="REQUIRED"),
    # active=false is a tombstone: the group was deleted (only ever when it had no
    # active members — a delete is rejected while members remain).
    bigquery.SchemaField("active", "BOOL", mode="REQUIRED"),
    bigquery.SchemaField("edited_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("edited_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("change_id", "STRING", mode="REQUIRED"),
]


def _group_log_ref(cfg: Settings) -> str:
    return sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_commodity_group_log_table)


def _catalog_log_ref(cfg: Settings) -> str:
    return sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_commodity_catalog_log_table)


def ensure_commodity_group_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the append-only groups registry if missing (clustered by group_id).
    Idempotent — called on first write."""
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = _group_log_ref(cfg)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=COMMODITY_GROUP_LOG_SCHEMA)
    table.clustering_fields = ["group_id"]
    bq.create_table(table, exists_ok=True)
    logger.info("Commodity-group registry ready at %s", table_fqn)
    return table_fqn


def _current_groups(bq: bigquery.Client, table_fqn: str) -> dict[str, str]:
    """Current active ``{group_id: group_name}`` (latest-wins). ``{}`` when the registry
    table doesn't exist yet."""
    sql = f"""
        select group_id, group_name from (
          select group_id, group_name, active, row_number() over (
            partition by group_id order by edited_at desc, change_id desc
          ) as _rn
          from `{table_fqn}`
        ) where _rn = 1 and active
    """
    try:
        return {r.group_id: r.group_name for r in bq.query(sql).result()}
    except NotFound:
        return {}


def _active_member_rows(bq: bigquery.Client, catalog_fqn: str, group_id: str) -> list:
    """Current ACTIVE catalog entries whose commodity_id == group_id (the group's
    members), with the fields needed to re-upsert them on a rename. ``[]`` when the
    catalog log doesn't exist yet."""
    sql = f"""
        select codigo_commodity, banco, descricao_commodity, ciclo_de_vida, code_prefix
        from (
          select *, row_number() over (
            partition by codigo_commodity, banco order by edited_at desc, change_id desc
          ) as _rn
          from `{catalog_fqn}` where commodity_id = @group_id
        ) where _rn = 1 and active
    """
    params = [bigquery.ScalarQueryParameter("group_id", "STRING", group_id)]
    try:
        job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
        return list(job.result())
    except NotFound:
        return []


def record_group(
    group_name: str,
    headers: Mapping[str, str],
    *,
    group_id: str | None = None,
    change_id: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Create a group (``group_id`` omitted → a NEW group, possibly empty) or RENAME an
    existing one (``group_id`` given). Create rejects a duplicate group_id; rename
    re-stamps the new name onto the group's member catalog entries so downstream reads
    (which use the entry's ``agrupamento``) stay consistent. IAP author + optional
    change_id idempotency. Raises ValueError (→ HTTP 400) on a bad/duplicate name."""
    cfg = settings or get_settings()
    group_name = (group_name or "").strip()
    if not group_name:
        raise ValueError("O nome do agrupamento é obrigatório.")
    if len(group_name) > MAX_NOTE_LEN:
        raise ValueError(f"O nome do agrupamento excede {MAX_NOTE_LEN} caracteres.")

    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _group_log_ref(cfg)
    ensure_commodity_group_log_table(cfg, bq)

    current = _current_groups(bq, table_fqn)
    renaming = group_id is not None
    group_id = (group_id or curation._slug(group_name)).strip() or None
    if not group_id:
        raise ValueError("Não foi possível gerar o group_id a partir do nome.")
    if renaming and group_id not in current:
        raise ValueError(f"O agrupamento {group_id!r} não existe (nada a renomear).")
    if not renaming and group_id in current:
        raise ValueError(f"O agrupamento {group_name!r} já existe.")

    if supplied and _change_id_seen(bq, table_fqn, change_id):
        return _group_row(group_id, group_name, True, edited_by, change_id, deduped=True)

    _insert_group_row(bq, table_fqn, group_id, group_name, True, edited_by, change_id)
    logger.info("Group: %s -> %r by %s", group_id, group_name, edited_by)

    # RENAME: re-stamp the new name onto the group's member catalog entries (the entry's
    # denormalized agrupamento is what dim_commodity_catalog / the crosswalk read).
    if renaming:
        members = _active_member_rows(bq, _catalog_log_ref(cfg), group_id)
        for m in members:
            curation.record_commodity_catalog(
                str(m.codigo_commodity),
                m.banco,
                headers,
                agrupamento=group_name,
                descricao_commodity=m.descricao_commodity,
                ciclo_de_vida=m.ciclo_de_vida,
                code_prefix=str(m.code_prefix),
                commodity_id=group_id,
                settings=cfg,
                client=bq,
                invalidate_cache=False,
            )
        if members:
            logger.info("Group %s rename re-tagged %d member(s)", group_id, len(members))

    if invalidate_cache:
        invalidate_group_cache()
    return _group_row(group_id, group_name, True, edited_by, change_id, deduped=False)


def delete_group(
    group_id: str,
    headers: Mapping[str, str],
    *,
    change_id: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Tombstone (soft-delete) a group. REJECTED while the group still has active
    catalog members — the researcher reassigns/removes them first (never a silent
    cascade that would orphan Gold data). Raises ValueError (→ HTTP 400)."""
    cfg = settings or get_settings()
    group_id = (group_id or "").strip()
    if not group_id:
        raise ValueError("group_id é obrigatório.")
    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _group_log_ref(cfg)
    ensure_commodity_group_log_table(cfg, bq)

    current = _current_groups(bq, table_fqn)
    if group_id not in current:
        raise ValueError(f"O agrupamento {group_id!r} não existe (nada a excluir).")
    members = _active_member_rows(bq, _catalog_log_ref(cfg), group_id)
    if members:
        raise ValueError(
            f"O agrupamento {current[group_id]!r} ainda tem {len(members)} commodity(ies) — "
            "reatribua ou remova antes de excluir o agrupamento."
        )

    name = current[group_id]
    if supplied and _change_id_seen(bq, table_fqn, change_id):
        return _group_row(group_id, name, False, edited_by, change_id, deduped=True)
    _insert_group_row(bq, table_fqn, group_id, name, False, edited_by, change_id)
    logger.info("Group: %s -> deleted (tombstone) by %s", group_id, edited_by)
    if invalidate_cache:
        invalidate_group_cache()
    return _group_row(group_id, name, False, edited_by, change_id, deduped=False)


def _insert_group_row(bq, table_fqn, group_id, group_name, active, edited_by, change_id) -> None:
    """Append one group-registry row with a server-side timestamp (parameterized DML)."""
    sql = f"""
        insert into `{table_fqn}`
            (group_id, group_name, active, edited_by, edited_at, change_id)
        values
            (@group_id, @group_name, @active, @edited_by, current_timestamp(), @change_id)
    """
    p = bigquery.ScalarQueryParameter
    params = [
        p("group_id", "STRING", group_id),
        p("group_name", "STRING", group_name),
        p("active", "BOOL", active),
        p("edited_by", "STRING", edited_by),
        p("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def _group_row(group_id, group_name, active, edited_by, change_id, *, deduped) -> dict:
    """The written/echoed group row dict (shared by the write + dedup paths)."""
    return {
        "group_id": group_id,
        "group_name": group_name,
        "active": active,
        "edited_by": edited_by,
        "change_id": change_id,
        "deduped": deduped,
    }


def invalidate_group_cache() -> None:
    """Drop the cached group + catalog reads (a rename changes member names) — best-effort."""
    for fn in (gateway.fetch_commodity_groups, gateway.fetch_commodity_catalog):
        try:
            cache.delete_memoized(fn)
        except Exception as exc:  # pragma: no cover - cache unbound / backend down
            logger.warning("Could not invalidate commodity-group cache: %s", exc)
