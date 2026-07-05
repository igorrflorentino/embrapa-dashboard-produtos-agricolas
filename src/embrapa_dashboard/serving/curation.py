"""Curadoria (catalog) — what ENTERS and EXITS the dashboard.

This is the feature the project lead reserved the name "Curadoria" for: the
researcher-managed catalog of which commodities are in the dashboard, their
agrupamento (cross-source concept) and ciclo de vida (in/out). Each commodity is
registered by its EXACT source code (one code = one entry; no prefixes). It is the
editable successor to the version-controlled ``commodity_crosswalk`` seed (the seed
and this catalog are redundant — confirmed on real data; the catalog becomes the
single source of truth and ``gold_produto_agrupamento`` reads it).

NOT to be confused with ``serving/attribute_engineering.py`` (the FROZEN feature
that builds derived columns — per-code industrialization + market-nature). Both
reuse the shared primitives in ``serving/research_inputs.py``.

Design (honouring the lead's decisions):
  * **Append-only** log (``research_inputs.produto_catalog_log``): every edit is
    an immutable, IAP-attributed row; the CURRENT catalog is the latest row per
    ``(codigo_produto, banco)``. **No row is ever destroyed** — a removal appends
    an ``active=false`` tombstone (the entry leaves the catalog → its Gold data
    becomes an orphan, handled non-destructively by the lifecycle, never auto-deleted).
  * **Composite key** ``(codigo_produto, banco)``: both required — a blank either
    breaks the key, so the writer REJECTS it (fail loud) rather than ignoring it.
  * **Exact code only** (no prefixes): a NEW entry's ``codigo_produto`` must be a
    REAL product code in the source's Gold — the writer validates existence against
    ``gateway.fetch_source_code_stats`` (the Gold code universe, NOT the visibility-gated
    serving mart) and REJECTS a code that doesn't exist (an update to an already-active
    entry is exempt). ``gold_produto_agrupamento`` / the visibility gate
    match on ``code = codigo_produto`` (equality, not ``LIKE``), so there is no
    prefix fan-out to double-count.
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

from embrapa_dashboard.config import Settings, get_settings
from embrapa_dashboard.gcp.bigquery import ensure_dataset
from embrapa_dashboard.serving import gateway
from embrapa_dashboard.serving import sql as sqlbuild
from embrapa_dashboard.serving.cache import cache
from embrapa_dashboard.serving.iap import author_email_from_headers
from embrapa_dashboard.serving.research_inputs import (
    MAX_NOTE_LEN,
    MAX_STAGE_LEN,
    _bq_client,
    _change_id_seen,
    _resolve_change_id,
)

logger = logging.getLogger(__name__)

# The resource id of the commodity catalog in the per-catalog allowlist.
PRODUTO_CATALOG_RESOURCE = "produto_catalog"

# Append-only commodity-catalog log. Explicit schema (autodetect drifts silently).
PRODUTO_CATALOG_LOG_SCHEMA = [
    bigquery.SchemaField("codigo_produto", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("banco", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("agrupamento", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("descricao_produto", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ciclo_de_vida", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("agrupamento_id", "STRING", mode="NULLABLE"),
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
    return sqlbuild.table_ref(cfg, "bq_research_inputs_dataset", cfg.bq_produto_catalog_log_table)


def ensure_produto_catalog_log_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the append-only commodity-catalog log if missing (clustered by the
    key). Idempotent — called on first write."""
    cfg = settings or get_settings()
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_dataset(bq, f"{cfg.gcp_project_id}.{cfg.bq_research_inputs_dataset}", cfg.bq_location)
    table = bigquery.Table(table_fqn, schema=PRODUTO_CATALOG_LOG_SCHEMA)
    table.clustering_fields = ["banco", "codigo_produto"]
    bq.create_table(table, exists_ok=True)
    logger.info("Commodity-catalog log ready at %s", table_fqn)
    return table_fqn


def ensure_catalog_editors_table(
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
) -> str:
    """Create the per-catalog editor allowlist table if missing. Idempotent.

    Console-managed: ``INSERT (resource, email) VALUES ('produto_catalog', 'a@x')``
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
    """ASCII slug of an agrupamento → agrupamento_id (matches the seed's slugs:
    'Castanha-do-pará' → 'castanha_do_para', 'Açaí' → 'acai')."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# The Ciclo de Vida (F7) vocabulary — MUST stay in lockstep with the UI dropdown
# (frontend/src/ui/ViewCadastroProdutos.jsx `_CC_CICLO`) and the dbt visibility gate
# (dbt/models/core/dim_produto_visibility.sql, which hides exactly CICLO_DE_VIDA_OCULTO).
# Validating it server-side turns a reword-in-one-place into a LOUD 400 instead of a SILENT
# fail-open of the visibility gate (the three layers couple on this exact pt-BR literal).
CICLO_DE_VIDA_VISIVEL = "Fazer Ingestão e deixar disponível"
CICLO_DE_VIDA_OCULTO = "Fazer Ingestão mas deixar indisponível"
_CICLO_DE_VIDA_VALUES = frozenset({CICLO_DE_VIDA_VISIVEL, CICLO_DE_VIDA_OCULTO})


def _validate_catalog_edit(codigo_produto: str, banco: str, ciclo_de_vida: str | None) -> None:
    """The composite key (codigo_produto, banco) is required — a blank either breaks
    the key, so we REJECT (fail loud) instead of silently dropping the row. Messages are
    pt-BR: a researcher reads them (the route surfaces ``str(exc)`` on a 400)."""
    if not codigo_produto or not banco:
        raise ValueError("codigo_produto e banco são obrigatórios (a chave do catálogo).")
    if ciclo_de_vida is not None and len(ciclo_de_vida) > MAX_STAGE_LEN:
        raise ValueError(f"ciclo_de_vida excede {MAX_STAGE_LEN} caracteres.")
    if ciclo_de_vida and ciclo_de_vida not in _CICLO_DE_VIDA_VALUES:
        raise ValueError(
            f"ciclo_de_vida {ciclo_de_vida!r} inválido — use exatamente um de "
            f"{sorted(_CICLO_DE_VIDA_VALUES)} (mantém o gate de visibilidade em sincronia)."
        )


# Catalog banco token → the long source id. Doubles as the allowlist of the 5 valid catalog
# banco tokens (its keys) that _assert_code_exists validates against before the Gold read.
_BANCO_TO_SOURCE = {
    "pevs": "ibge_pevs",
    "pam": "ibge_pam",
    "ppm": "ibge_ppm",
    "comex": "mdic_comex",
    "comtrade": "un_comtrade",
}


def _is_active_entry(bq: bigquery.Client, table_fqn: str, codigo_produto: str, banco: str) -> bool:
    """Whether (codigo_produto, banco) is CURRENTLY an active catalog entry (latest-wins)
    — i.e. this write is an UPDATE, not a new registration. ``False`` when the log table
    doesn't exist yet."""
    sql = f"""
        select active from (
          select active, row_number() over (
            partition by codigo_produto, banco order by edited_at desc, change_id desc
          ) as _rn
          from `{table_fqn}`
          where codigo_produto = @codigo and banco = @banco
        ) where _rn = 1
    """
    params = [
        bigquery.ScalarQueryParameter("codigo", "STRING", codigo_produto),
        bigquery.ScalarQueryParameter("banco", "STRING", banco),
    ]
    try:
        rows = list(
            bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        )
    except NotFound:
        return False
    return bool(rows) and bool(rows[0].active)


def _assert_code_exists(
    bq: bigquery.Client, table_fqn: str, codigo_produto: str, banco: str
) -> None:
    """A NEW catalog entry's code MUST be a real product code in the source's Gold — you
    can't register a commodity whose code doesn't exist in the data. An UPDATE to an
    already-active entry is always allowed (validated on add; its Gold data may have since
    changed, and you must still be able to edit its ciclo/agrupamento). Degrades to a no-op
    when the source has no product list yet (table not built) rather than blocking. Fail
    loud (400, pt-BR) with a hint.

    Validates against the Gold code universe (``fetch_source_code_stats``, keyed by the
    short banco token) rather than the serving mart: the mart has the F7 visibility gate
    baked in at BUILD time, so a code cataloged as *indisponível* then tombstoned could not
    be re-registered until the next nightly dbt build even though it demonstrably exists in
    Gold. Reading Gold directly avoids that one-build-cycle re-add lag."""
    if _is_active_entry(bq, table_fqn, codigo_produto, banco):
        return  # update of an existing entry — not a new registration
    source = _BANCO_TO_SOURCE.get(banco)
    if source is None:
        # An unknown banco token would otherwise write a junk row that never joins in
        # gold_produto_agrupamento (source ∈ pevs/comex/comtrade) — silent orphaned data.
        # No other layer validates the banco, so reject it loudly here.
        raise ValueError(f"banco {banco!r} inválido — use um de {sorted(_BANCO_TO_SOURCE)}.")
    try:
        stats = gateway.fetch_source_code_stats(banco)
    except NotFound:
        return  # source Gold table not built yet — don't block the first catalog write
    if stats is None or stats.empty:
        return
    codes = {str(r.code) for r in stats.itertuples()}
    if codigo_produto not in codes:
        raise ValueError(
            f"O código {codigo_produto!r} não existe no banco {banco} — cadastre apenas "
            f"códigos reais da fonte (o banco tem {len(codes):,} códigos disponíveis)."
        )


def record_produto_catalog(
    codigo_produto: str,
    banco: str,
    headers: Mapping[str, str],
    *,
    agrupamento: str | None = None,
    descricao_produto: str | None = None,
    ciclo_de_vida: str | None = None,
    agrupamento_id: str | None = None,
    change_id: str | None = None,
    settings: Settings | None = None,
    client: bigquery.Client | None = None,
    invalidate_cache: bool = True,
) -> dict:
    """Append one commodity-catalog edit (upsert by latest-wins). IAP author capture +
    read-after-write + optional ``change_id`` idempotency, mirroring the
    attribute-engineering writers. Each commodity is registered by its EXACT source code
    (no prefixes); ``agrupamento_id`` defaults to the agrupamento slug. Validates the key,
    the agrupamento, and — for a NEW entry — that the code actually EXISTS in the source's
    Gold; raises ValueError on a bad key / over-length / a code that doesn't exist."""
    cfg = settings or get_settings()
    codigo_produto = (codigo_produto or "").strip()
    banco = (banco or "").strip()
    ciclo_de_vida = ciclo_de_vida.strip() if ciclo_de_vida else ciclo_de_vida
    _validate_catalog_edit(codigo_produto, banco, ciclo_de_vida)
    agrupamento = agrupamento.strip() if agrupamento else agrupamento
    agrupamento_id = (agrupamento_id or _slug(agrupamento)).strip() or None
    # agrupamento names the commodity (agrupamento_nome) AND seeds agrupamento_id; both
    # are NOT NULL downstream (dim_produto_catalog → gold_produto_agrupamento). A
    # blank one yields NULLs that fail the nightly prod ``dbt build`` not_null tests —
    # so fail loud HERE (a 400 the researcher can fix), never at build time.
    if not agrupamento_id or not agrupamento:
        raise ValueError("agrupamento é obrigatório (nomeia o produto e gera o agrupamento_id).")
    if len(agrupamento) > MAX_NOTE_LEN:
        raise ValueError(f"agrupamento excede {MAX_NOTE_LEN} caracteres.")
    if descricao_produto is not None and len(descricao_produto) > MAX_NOTE_LEN:
        raise ValueError(f"descricao_produto excede {MAX_NOTE_LEN} caracteres.")

    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_produto_catalog_log_table(cfg, bq)

    # A new entry's code must be a real product code in the source's Gold (an update to
    # an already-active entry is exempt). Read current state AFTER ensure (table exists).
    _assert_code_exists(bq, table_fqn, codigo_produto, banco)

    if supplied and _change_id_seen(bq, table_fqn, change_id):
        logger.info(
            "Catalog: duplicate change_id %s ignored (%s:%s)", change_id, banco, codigo_produto
        )
        return _catalog_row(
            codigo_produto,
            banco,
            agrupamento,
            descricao_produto,
            ciclo_de_vida,
            agrupamento_id,
            True,
            edited_by,
            change_id,
            deduped=True,
        )
    _insert_catalog_row(
        bq,
        table_fqn,
        codigo_produto,
        banco,
        agrupamento,
        descricao_produto,
        ciclo_de_vida,
        agrupamento_id,
        True,
        edited_by,
        change_id,
    )
    logger.info("Catalog: %s:%s -> active by %s", banco, codigo_produto, edited_by)
    if invalidate_cache:
        invalidate_produto_catalog_cache()
    return _catalog_row(
        codigo_produto,
        banco,
        agrupamento,
        descricao_produto,
        ciclo_de_vida,
        agrupamento_id,
        True,
        edited_by,
        change_id,
        deduped=False,
    )


def remove_produto_catalog(
    codigo_produto: str,
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
    codigo_produto = (codigo_produto or "").strip()
    banco = (banco or "").strip()
    _validate_catalog_edit(codigo_produto, banco, None)
    edited_by = author_email_from_headers(
        headers, dev_fallback=cfg.curation_dev_author, audience=cfg.iap_audience
    )
    change_id, supplied = _resolve_change_id(change_id)
    bq = client or _bq_client(cfg)
    table_fqn = _catalog_log_ref(cfg)
    ensure_produto_catalog_log_table(cfg, bq)
    if supplied and _change_id_seen(bq, table_fqn, change_id):
        return _catalog_row(
            codigo_produto,
            banco,
            None,
            None,
            None,
            None,
            False,
            edited_by,
            change_id,
            deduped=True,
        )
    # A tombstone must reference a currently-ACTIVE entry (removing a never-cataloged key
    # would write a phantom tombstone → a false orphan). Orphan detection now keys off the
    # exact codigo_produto (no prefixes).
    if not _is_active_entry(bq, table_fqn, codigo_produto, banco):
        raise ValueError(
            f"{codigo_produto!r} não está cadastrada (ativa) em {banco!r} — nada a remover."
        )
    _insert_catalog_row(
        bq,
        table_fqn,
        codigo_produto,
        banco,
        None,
        None,
        None,
        None,
        False,
        edited_by,
        change_id,
    )
    logger.info("Catalog: %s:%s -> removed (tombstone) by %s", banco, codigo_produto, edited_by)
    if invalidate_cache:
        invalidate_produto_catalog_cache()
    return _catalog_row(
        codigo_produto,
        banco,
        None,
        None,
        None,
        None,
        False,
        edited_by,
        change_id,
        deduped=False,
    )


def _insert_catalog_row(
    bq,
    table_fqn,
    codigo_produto,
    banco,
    agrupamento,
    descricao_produto,
    ciclo_de_vida,
    agrupamento_id,
    active,
    edited_by,
    change_id,
) -> None:
    """Append one catalog row with a server-side timestamp (parameterized DML)."""
    sql = f"""
        insert into `{table_fqn}`
            (codigo_produto, banco, agrupamento, descricao_produto,
             ciclo_de_vida, agrupamento_id, active, edited_by, edited_at, change_id)
        values
            (@codigo_produto, @banco, @agrupamento, @descricao_produto,
             @ciclo_de_vida, @agrupamento_id, @active, @edited_by,
             current_timestamp(), @change_id)
    """
    p = bigquery.ScalarQueryParameter
    params = [
        p("codigo_produto", "STRING", codigo_produto),
        p("banco", "STRING", banco),
        p("agrupamento", "STRING", agrupamento),
        p("descricao_produto", "STRING", descricao_produto),
        p("ciclo_de_vida", "STRING", ciclo_de_vida),
        p("agrupamento_id", "STRING", agrupamento_id),
        p("active", "BOOL", active),
        p("edited_by", "STRING", edited_by),
        p("change_id", "STRING", change_id),
    ]
    bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def _catalog_row(
    codigo_produto,
    banco,
    agrupamento,
    descricao_produto,
    ciclo_de_vida,
    agrupamento_id,
    active,
    edited_by,
    change_id,
    *,
    deduped,
) -> dict:
    """The written/echoed catalog row dict (shared by the write + dedup paths)."""
    return {
        "codigo_produto": codigo_produto,
        "banco": banco,
        "agrupamento": agrupamento,
        "descricao_produto": descricao_produto,
        "ciclo_de_vida": ciclo_de_vida,
        "agrupamento_id": agrupamento_id,
        "active": active,
        "edited_by": edited_by,
        "change_id": change_id,
        "deduped": deduped,
    }


def invalidate_produto_catalog_cache() -> None:
    """Drop the cached current-catalog read so the next query is fresh (best-effort).

    Also drops ``fetch_orphan_produtos``: the orphan worklist derives its tombstones
    from the SAME produto_catalog_log, so a catalog write (especially a removal) must
    refresh it too — otherwise the Descontinuados view lags read-after-write up to its TTL.
    Same reasoning for ``fetch_agrupamentos``: each group's ``n_members`` is computed from
    that same catalog log, so an add/remove must refresh the groups list too — otherwise
    the delete-blocking hint (n_members) lags read-after-write up to its TTL.
    """
    for fn in (
        gateway.fetch_produto_catalog,
        gateway.fetch_orphan_produtos,
        gateway.fetch_agrupamentos,
    ):
        try:
            cache.delete_memoized(fn)
        except Exception as exc:  # pragma: no cover - cache unbound / backend down
            logger.warning("Could not invalidate commodity-catalog cache: %s", exc)
