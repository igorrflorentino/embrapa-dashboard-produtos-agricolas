"""Curadoria (catalog) — what ENTERS and EXITS the dashboard.

This is the feature the project lead reserved the name "Curadoria" for: the
researcher-managed catalog of which commodities are in the dashboard, their
agrupamento (cross-source concept), industrialização, ciclo de vida (in/out) and
the ``code_prefix`` used for the cross-source bridge. It is the editable successor
to the version-controlled ``commodity_crosswalk`` seed (the seed and this catalog
are redundant — confirmed on real data; the catalog becomes the single source of
truth and ``gold_commodity_crosswalk`` reads it).

NOT to be confused with ``serving/attribute_engineering.py`` (the FROZEN feature
that builds derived columns — per-code industrialization + market-nature). Both
reuse the shared primitives in ``serving/research_inputs.py``.

Design (honouring the lead's decisions):
  * **Append-only** log (``research_inputs.commodity_catalog_log``): every edit is
    an immutable, IAP-attributed row; the CURRENT catalog is the latest row per
    ``(codigo_commodity, banco)``. **No row is ever destroyed** — a removal appends
    an ``active=false`` tombstone (the entry leaves the catalog → its Gold data
    becomes an orphan, handled non-destructively by the lifecycle, never auto-deleted).
  * **Composite key** ``(codigo_commodity, banco)``: both required — a blank either
    breaks the key, so the writer REJECTS it (fail loud) rather than ignoring it.
  * **``code_prefix`` is KEPT** (the lead's decision): coarse prefixes auto-absorb
    future sub-codes. Because overlapping prefixes within a banco silently DOUBLE
    every downstream sum (today caught only by the dbt ``unique_combination`` test),
    the writer validates **prefix-disjointness on write** — the one non-obvious gate
    that makes this seed safe to hand to researchers.
  * **Per-catalog allowlist** (``research_inputs.catalog_editors`` keyed by resource):
    each cadastro has its OWN authorized editors, distinct from the
    attribute-engineering ``curators`` table.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from embrapa_commodities.config import Settings, get_settings
from embrapa_commodities.gcp.bigquery import ensure_dataset
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache
from embrapa_commodities.serving.iap import author_email_from_headers
from embrapa_commodities.serving.research_inputs import (
    MAX_NOTE_LEN,
    MAX_STAGE_LEN,
    _bq_client,
    _change_id_seen,
    _resolve_change_id,
)

logger = logging.getLogger(__name__)

# The resource id of the commodity catalog in the per-catalog allowlist.
COMMODITY_CATALOG_RESOURCE = "commodity_catalog"

# Append-only commodity-catalog log. Explicit schema (autodetect drifts silently).
COMMODITY_CATALOG_LOG_SCHEMA = [
    bigquery.SchemaField("codigo_commodity", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("banco", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agrupamento", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("descricao_commodity", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("industrializacao", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ciclo_de_vida", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("code_prefix", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("commodity_id", "STRING", mode="NULLABLE"),
    # active=false is a tombstone: the entry has left the catalog (→ Gold orphan).
    bigquery.SchemaField("active", "BOOL", mode="REQUIRED"),
    bigquery.SchemaField("edited_by", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("edited_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("change_id", "STRING", mode="REQUIRED"),
]

# Per-CATALOG editor allowlist (one row per (resource, email)).
CATALOG_EDITORS_SCHEMA = [
    bigquery.SchemaField("resource", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("added_by", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("added_at", "TIMESTAMP", mode="NULLABLE"),
]


def _catalog_log_ref(cfg: Settings) -> str:
    return sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_commodity_catalog_log_table)


def ensure_commodity_catalog_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the append-only commodity-catalog log if missing (clustered by the
    key). Idempotent — called on first write."""
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=COMMODITY_CATALOG_LOG_SCHEMA)
    table.clustering_fields = ["banco", "codigo_commodity"]
    bq.create_table(table, exists_ok=True)
    logger.info("Commodity-catalog log ready at %s", table_fqn)
    return table_fqn


def ensure_catalog_editors_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the per-catalog editor allowlist table if missing. Idempotent.

    Console-managed: ``INSERT (resource, email) VALUES ('commodity_catalog', 'a@x')``
    to authorize an editor — no redeploy. Empty/absent → any IAP-authenticated caller
    may edit (the same open-by-default posture as the curators allowlist)."""
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_catalog_editors_table)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    bq.create_table(bigquery.Table(table_fqn, schema=CATALOG_EDITORS_SCHEMA), exists_ok=True)
    logger.info("Catalog-editors allowlist table ready at %s", table_fqn)
    return table_fqn


def _slug(name: str | None) -> str:
    """ASCII slug of an agrupamento → commodity_id (matches the seed's slugs:
    'Castanha-do-pará' → 'castanha_do_para', 'Açaí' → 'acai')."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# The Ciclo de Vida (F7) vocabulary — MUST stay in lockstep with the UI dropdown
# (frontend/src/ui/ViewCadastroCommodities.jsx `_CC_CICLO`) and the dbt visibility gate
# (dbt/models/core/dim_commodity_visibility.sql, which hides exactly CICLO_DE_VIDA_OCULTO).
# Validating it server-side turns a reword-in-one-place into a LOUD 400 instead of a SILENT
# fail-open of the visibility gate (the three layers couple on this exact pt-BR literal).
CICLO_DE_VIDA_VISIVEL = "Fazer Ingestão e deixar disponível"
CICLO_DE_VIDA_OCULTO = "Fazer Ingestão mas deixar indisponível"
_CICLO_DE_VIDA_VALUES = frozenset({CICLO_DE_VIDA_VISIVEL, CICLO_DE_VIDA_OCULTO})


def _validate_catalog_edit(codigo_commodity: str, banco: str, ciclo_de_vida: str | None) -> None:
    """The composite key (codigo_commodity, banco) is required — a blank either breaks
    the key, so we REJECT (fail loud) instead of silently dropping the row. Messages are
    pt-BR: a researcher reads them (the route surfaces ``str(exc)`` on a 400)."""
    if not codigo_commodity or not banco:
        raise ValueError("codigo_commodity e banco são obrigatórios (a chave do catálogo).")
    if ciclo_de_vida is not None and len(ciclo_de_vida) > MAX_STAGE_LEN:
        raise ValueError(f"ciclo_de_vida excede {MAX_STAGE_LEN} caracteres.")
    if ciclo_de_vida and ciclo_de_vida not in _CICLO_DE_VIDA_VALUES:
        raise ValueError(
            f"ciclo_de_vida {ciclo_de_vida!r} inválido — use exatamente um de "
            f"{sorted(_CICLO_DE_VIDA_VALUES)} (mantém o gate de visibilidade em sincronia)."
        )


def _current_prefixes(bq: bigquery.Client, table_fqn: str, banco: str) -> list[tuple[str, str]]:
    """Current active ``(codigo_commodity, code_prefix)`` for a banco (latest-wins).
    ``[]`` when the log table doesn't exist yet (the first write has no conflicts)."""
    sql = f"""
        select codigo_commodity, code_prefix from (
          select codigo_commodity, code_prefix, active, row_number() over (
            partition by codigo_commodity, banco order by edited_at desc, change_id desc
          ) as _rn
          from `{table_fqn}` where banco = @banco
        ) where _rn = 1 and active
    """
    params = [bigquery.ScalarQueryParameter("banco", "STRING", banco)]
    try:
        job = bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
        return [(r.codigo_commodity, r.code_prefix) for r in job.result()]
    except NotFound:
        return []


def _assert_prefix_disjoint(
    codigo_commodity: str, code_prefix: str, existing: list[tuple[str, str]]
) -> None:
    """Reject a code_prefix that overlaps another active prefix in the SAME banco
    (one is a prefix of the other) — overlapping prefixes fan out the cross-source
    LEFT JOIN and SILENTLY DOUBLE every downstream sum. Updating the same key is fine.
    """
    for other_codigo, other_prefix in existing:
        if other_codigo == codigo_commodity:
            continue  # same entry being updated — not a conflict
        if code_prefix.startswith(other_prefix) or other_prefix.startswith(code_prefix):
            raise ValueError(
                f"O prefixo {code_prefix!r} se sobrepõe ao prefixo {other_prefix!r} "
                f"(commodity {other_codigo!r}) já cadastrado neste banco — prefixos "
                "sobrepostos duplicam as somas. Use prefixos disjuntos."
            )


def record_commodity_catalog(
    codigo_commodity: str,
    banco: str,
    headers: Mapping[str, str],
    *,
    agrupamento: str | None = None,
    descricao_commodity: str | None = None,
    industrializacao: str | None = None,
    ciclo_de_vida: str | None = None,
    code_prefix: str | None = None,
    commodity_id: str | None = None,
    change_id: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Append one commodity-catalog edit (upsert by latest-wins). IAP author capture +
    read-after-write + optional ``change_id`` idempotency, mirroring the
    attribute-engineering writers. ``code_prefix`` defaults to ``codigo_commodity`` and
    ``commodity_id`` to the agrupamento slug. Validates the key + prefix-disjointness;
    raises ValueError on a bad key / over-length / overlapping prefix."""
    cfg = settings or get_settings()
    codigo_commodity = (codigo_commodity or "").strip()
    banco = (banco or "").strip()
    ciclo_de_vida = ciclo_de_vida.strip() if ciclo_de_vida else ciclo_de_vida
    _validate_catalog_edit(codigo_commodity, banco, ciclo_de_vida)
    # code_prefix backs the cross-source ``LIKE prefix||'%'`` bridge. A blank one
    # (e.g. whitespace, which is truthy so the ``or codigo_commodity`` fallback is
    # skipped before .strip()) collapses to ``''`` → ``LIKE '%'`` → one commodity
    # absorbs EVERY code in the banco (silent fan-out). A LIKE wildcard ('%' or '_')
    # in the prefix breaks the match the same way. Reject both at the write gate.
    code_prefix = (code_prefix or codigo_commodity).strip()
    if not code_prefix:
        raise ValueError("code_prefix não pode ser vazio.")
    if "%" in code_prefix or "_" in code_prefix:
        raise ValueError("code_prefix não pode conter curingas LIKE ('%' ou '_').")
    agrupamento = agrupamento.strip() if agrupamento else agrupamento
    commodity_id = (commodity_id or _slug(agrupamento)).strip() or None
    # agrupamento names the commodity (commodity_name) AND seeds commodity_id; both
    # are NOT NULL downstream (dim_commodity_catalog → gold_commodity_crosswalk). A
    # blank one yields NULLs that fail the nightly prod ``dbt build`` not_null tests —
    # so fail loud HERE (a 400 the researcher can fix), never at build time.
    if not commodity_id or not agrupamento:
        raise ValueError("agrupamento é obrigatório (nomeia a commodity e gera o commodity_id).")
    if len(agrupamento) > MAX_NOTE_LEN:
        raise ValueError(f"agrupamento excede {MAX_NOTE_LEN} caracteres.")
    if descricao_commodity is not None and len(descricao_commodity) > MAX_NOTE_LEN:
        raise ValueError(f"descricao_commodity excede {MAX_NOTE_LEN} caracteres.")

    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_commodity_catalog_log_table(cfg, bq)

    # Prefix-disjointness guard (read current state AFTER ensure, so the table exists).
    _assert_prefix_disjoint(codigo_commodity, code_prefix, _current_prefixes(bq, table_fqn, banco))

    if supplied and _change_id_seen(bq, table_fqn, change_id):
        logger.info(
            "Catalog: duplicate change_id %s ignored (%s:%s)", change_id, banco, codigo_commodity
        )
        return _catalog_row(
            codigo_commodity,
            banco,
            agrupamento,
            descricao_commodity,
            industrializacao,
            ciclo_de_vida,
            code_prefix,
            commodity_id,
            True,
            edited_by,
            change_id,
            deduped=True,
        )
    _insert_catalog_row(
        bq,
        table_fqn,
        codigo_commodity,
        banco,
        agrupamento,
        descricao_commodity,
        industrializacao,
        ciclo_de_vida,
        code_prefix,
        commodity_id,
        True,
        edited_by,
        change_id,
    )
    logger.info("Catalog: %s:%s -> active by %s", banco, codigo_commodity, edited_by)
    if invalidate_cache:
        invalidate_commodity_catalog_cache()
    return _catalog_row(
        codigo_commodity,
        banco,
        agrupamento,
        descricao_commodity,
        industrializacao,
        ciclo_de_vida,
        code_prefix,
        commodity_id,
        True,
        edited_by,
        change_id,
        deduped=False,
    )


def remove_commodity_catalog(
    codigo_commodity: str,
    banco: str,
    headers: Mapping[str, str],
    *,
    change_id: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Append an ``active=false`` TOMBSTONE — the entry leaves the catalog (its Gold
    data becomes an orphan, handled non-destructively by the lifecycle; NEVER auto-
    deleted). The historical rows stay; only the current state flips to removed."""
    cfg = settings or get_settings()
    codigo_commodity = (codigo_commodity or "").strip()
    banco = (banco or "").strip()
    _validate_catalog_edit(codigo_commodity, banco, None)
    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_commodity_catalog_log_table(cfg, bq)
    if supplied and _change_id_seen(bq, table_fqn, change_id):
        return _catalog_row(
            codigo_commodity,
            banco,
            None,
            None,
            None,
            None,
            codigo_commodity,
            None,
            False,
            edited_by,
            change_id,
            deduped=True,
        )
    # A tombstone must reference a currently-ACTIVE entry (removing a never-cataloged
    # key would write a phantom tombstone → a false orphan), and must carry that entry's
    # REAL code_prefix — orphan detection keys off the tombstone's prefix, so writing the
    # codigo here would blind detection for any coarse-prefix entry (codigo != prefix).
    active = _current_prefixes(bq, table_fqn, banco)
    code_prefix = next((pfx for cod, pfx in active if cod == codigo_commodity), None)
    if code_prefix is None:
        raise ValueError(
            f"{codigo_commodity!r} não está cadastrada (ativa) em {banco!r} — nada a remover."
        )
    _insert_catalog_row(
        bq,
        table_fqn,
        codigo_commodity,
        banco,
        None,
        None,
        None,
        None,
        code_prefix,
        None,
        False,
        edited_by,
        change_id,
    )
    logger.info("Catalog: %s:%s -> removed (tombstone) by %s", banco, codigo_commodity, edited_by)
    if invalidate_cache:
        invalidate_commodity_catalog_cache()
    return _catalog_row(
        codigo_commodity,
        banco,
        None,
        None,
        None,
        None,
        code_prefix,
        None,
        False,
        edited_by,
        change_id,
        deduped=False,
    )


def _insert_catalog_row(
    bq,
    table_fqn,
    codigo_commodity,
    banco,
    agrupamento,
    descricao_commodity,
    industrializacao,
    ciclo_de_vida,
    code_prefix,
    commodity_id,
    active,
    edited_by,
    change_id,
) -> None:
    """Append one catalog row with a server-side timestamp (parameterized DML)."""
    sql = f"""
        insert into `{table_fqn}`
            (codigo_commodity, banco, agrupamento, descricao_commodity, industrializacao,
             ciclo_de_vida, code_prefix, commodity_id, active, edited_by, edited_at, change_id)
        values
            (@codigo_commodity, @banco, @agrupamento, @descricao_commodity, @industrializacao,
             @ciclo_de_vida, @code_prefix, @commodity_id, @active, @edited_by,
             current_timestamp(), @change_id)
    """
    p = bigquery.ScalarQueryParameter
    params = [
        p("codigo_commodity", "STRING", codigo_commodity),
        p("banco", "STRING", banco),
        p("agrupamento", "STRING", agrupamento),
        p("descricao_commodity", "STRING", descricao_commodity),
        p("industrializacao", "STRING", industrializacao),
        p("ciclo_de_vida", "STRING", ciclo_de_vida),
        p("code_prefix", "STRING", code_prefix),
        p("commodity_id", "STRING", commodity_id),
        p("active", "BOOL", active),
        p("edited_by", "STRING", edited_by),
        p("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def _catalog_row(
    codigo_commodity,
    banco,
    agrupamento,
    descricao_commodity,
    industrializacao,
    ciclo_de_vida,
    code_prefix,
    commodity_id,
    active,
    edited_by,
    change_id,
    *,
    deduped,
) -> dict:
    """The written/echoed catalog row dict (shared by the write + dedup paths)."""
    return {
        "codigo_commodity": codigo_commodity,
        "banco": banco,
        "agrupamento": agrupamento,
        "descricao_commodity": descricao_commodity,
        "industrializacao": industrializacao,
        "ciclo_de_vida": ciclo_de_vida,
        "code_prefix": code_prefix,
        "commodity_id": commodity_id,
        "active": active,
        "edited_by": edited_by,
        "change_id": change_id,
        "deduped": deduped,
    }


def invalidate_commodity_catalog_cache() -> None:
    """Drop the cached current-catalog read so the next query is fresh (best-effort)."""
    try:
        cache.delete_memoized(gateway.fetch_commodity_catalog)
    except Exception as exc:  # pragma: no cover - cache unbound / backend down
        logger.warning("Could not invalidate commodity-catalog cache: %s", exc)
