"""Curadoria (catalog) seam readers/writers — what ENTERS and EXITS the dashboard.

The seam layer over ``serving/curation.py``: the current commodity catalog (for the
admin UI), the append-only upsert/remove writers (IAP author capture), and the
per-catalog editor allowlist. Reads degrade gracefully to an EMPTY catalog when the
log table doesn't exist yet (no catalog configured) — distinct from a transient
error, which propagates. Imports only the gateway (never ``seam``), so the import
graph stays acyclic; ``seam`` re-exports the public surface.

Not to be confused with ``seam_attribute_engineering`` (the FROZEN derived-columns
feature). This is the catalog the lead reserved the name "Curadoria" for.
"""

from __future__ import annotations

from google.api_core.exceptions import NotFound

from embrapa_commodities.serving import gateway

COMMODITY_CATALOG_RESOURCE = "commodity_catalog"


def _clean(x):
    """A NULL STRING cell reads back from BigQuery as float('nan'); normalize it to
    None so JSON serialization and the ``sorted(groups.items())`` grouping don't choke
    on a float mixed with strings (a catalog entry may legitimately have no
    agrupamento/descrição/ciclo)."""
    return None if (isinstance(x, float) and x != x) else x


# Catalog banco token → the long source id ``fetch_products`` expects, so the editor can
# show each code's ORIGINAL source description (IBGE product / NCM / HS6 name).
_BANCO_TO_SOURCE = {
    "pevs": "ibge_pevs",
    "pam": "ibge_pam",
    "ppm": "ibge_ppm",
    "comex": "mdic_comex",
    "comtrade": "un_comtrade",
}


def catalog_worklist(banco: str | None = None) -> dict:
    """The current commodity catalog (latest-wins, active) — backs the admin editor.

    Returns ``{entries, total, by_agrupamento}``; the per-Agrupamento grouping backs
    the lead's per-Agrupamento edit grain. Empty (not an error) before the catalog
    exists, so the editor renders before the first write."""
    try:
        df = gateway.fetch_commodity_catalog(banco)
    except NotFound:
        # Log table genuinely absent (no catalog yet) — render empty. Any OTHER error
        # propagates instead of being masked as "not configured".
        return {"entries": [], "total": 0, "by_agrupamento": []}
    if df is None or df.empty:
        return {"entries": [], "total": 0, "by_agrupamento": []}
    entries = [
        {
            "codigo_commodity": str(r.codigo_commodity),
            "banco": r.banco,
            "agrupamento": _clean(r.agrupamento),
            "descricao_commodity": _clean(r.descricao_commodity),
            "ciclo_de_vida": _clean(r.ciclo_de_vida),
            "code_prefix": str(r.code_prefix),
            "commodity_id": _clean(r.commodity_id),
        }
        for r in df.itertuples()
    ]
    # Attach the source's ORIGINAL product description per (banco, codigo) — the name the
    # source (IBGE/COMEX/Comtrade) gives that code — so a bare numeric code isn't opaque.
    # Read once per source (memoized). A code that isn't an EXACT source code (a coarse
    # prefix registered for a group) has no single description → left None.
    source_names: dict[str, dict] = {}
    for b in {e["banco"] for e in entries}:
        src = _BANCO_TO_SOURCE.get(b)
        if not src:
            continue
        try:
            pdf = gateway.fetch_products(src)
        except NotFound:
            continue
        if pdf is not None and not pdf.empty:
            source_names[b] = {str(p.code): p.name for p in pdf.itertuples()}
    for e in entries:
        e["descricao_fonte"] = source_names.get(e["banco"], {}).get(e["codigo_commodity"])
    groups: dict = {}
    for e in entries:
        groups.setdefault(e["agrupamento"] or "—", []).append(e)
    by_agrupamento = [
        {"agrupamento": k, "n": len(v), "bancos": sorted({e["banco"] for e in v})}
        for k, v in sorted(groups.items())
    ]
    return {"entries": entries, "total": len(entries), "by_agrupamento": by_agrupamento}


def record_catalog_entry(payload: dict) -> dict:
    """Upsert one catalog entry from a request body. Author from the IAP header (dev
    fallback per config). Wraps the verified writer; raises ValueError on a bad key /
    over-length / overlapping prefix (→ HTTP 400)."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import curation

    headers = dict(request.headers) if has_request_context() else {}
    return curation.record_commodity_catalog(
        payload.get("codigo_commodity"),
        payload.get("banco"),
        headers,
        agrupamento=payload.get("agrupamento"),
        descricao_commodity=payload.get("descricao_commodity"),
        ciclo_de_vida=payload.get("ciclo_de_vida"),
        code_prefix=payload.get("code_prefix"),
        commodity_id=payload.get("commodity_id"),
        change_id=payload.get("change_id"),
    )


def remove_catalog_entry(payload: dict) -> dict:
    """Append an active=false tombstone for one (codigo_commodity, banco) — the entry
    leaves the catalog (NON-destructive: the Gold data becomes an orphan, never
    auto-deleted). Author from the IAP header."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import curation

    headers = dict(request.headers) if has_request_context() else {}
    return curation.remove_commodity_catalog(
        payload.get("codigo_commodity"),
        payload.get("banco"),
        headers,
        change_id=payload.get("change_id"),
    )


def group_worklist() -> dict:
    """The current commodity GROUPS (agrupamentos) registry — id, name and a live count
    of active catalog members (0 = an empty group; the UI blocks deleting a non-empty
    one). Backs the group-management UI. Empty (not an error) before the registry exists."""
    try:
        df = gateway.fetch_commodity_groups()
    except NotFound:
        return {"groups": [], "total": 0}
    if df is None or df.empty:
        return {"groups": [], "total": 0}
    groups = [
        {
            "group_id": r.group_id,
            "group_name": r.group_name,
            "n_members": int(r.n_members),
        }
        for r in df.itertuples()
    ]
    return {"groups": groups, "total": len(groups)}


def record_group(payload: dict) -> dict:
    """Create (group_id omitted) or RENAME (group_id given) a group. Author from the IAP
    header. Raises ValueError on a bad/duplicate name (→ HTTP 400)."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import commodity_groups

    headers = dict(request.headers) if has_request_context() else {}
    return commodity_groups.record_group(
        payload.get("group_name"),
        headers,
        group_id=payload.get("group_id"),
        change_id=payload.get("change_id"),
    )


def remove_group(payload: dict) -> dict:
    """Tombstone (delete) a group — rejected while it still has active members. Author
    from the IAP header. Raises ValueError (→ HTTP 400) when non-empty or absent."""
    from flask import has_request_context, request

    from embrapa_commodities.serving import commodity_groups

    headers = dict(request.headers) if has_request_context() else {}
    return commodity_groups.delete_group(
        payload.get("group_id"),
        headers,
        change_id=payload.get("change_id"),
    )


def catalog_editor_emails(resource: str = COMMODITY_CATALOG_RESOURCE) -> set[str]:
    """Lowercased editor emails authorized for a catalog resource; empty set when the
    allowlist table is absent (open by default). Any OTHER error propagates — a
    transient BQ/permission fault must NOT silently widen the gate to everyone."""
    try:
        df = gateway.fetch_catalog_editors(resource)
    except NotFound:
        return set()
    if df is None or df.empty:
        return set()
    return {str(e).strip().lower() for e in df["email"] if e}


def orphan_worklist() -> dict:
    """Orphan commodities — removed from the catalog with Gold data still lingering —
    overlaid with their Descontinuado lifecycle status (flagged date + deletion warning).
    Backs the editor's "Descontinuados" section. Empty (not an error) before any catalog
    exists. The orphan IS descontinuado by definition; ``flagged_at`` is None until the
    auto-marker has recorded it (the doctor/CLI cadence)."""
    from embrapa_commodities.serving.catalog_lifecycle import PURGE_WARNING

    try:
        orphans = gateway.fetch_orphan_commodities()
    except NotFound:
        orphans = None
    if orphans is None or orphans.empty:
        return {"orphans": [], "total": 0}
    try:
        status_df = gateway.fetch_lifecycle_status()
        status = (
            {(r.element_kind, r.banco, str(r.code)): r for r in status_df.itertuples()}
            if status_df is not None and not status_df.empty
            else {}
        )
    except NotFound:
        status = {}
    rows = []
    for o in orphans.itertuples():
        code = str(o.codigo_commodity)
        st = status.get(("commodity", o.banco, code))
        rows.append(
            {
                "codigo_commodity": code,
                "banco": o.banco,
                "agrupamento": o.agrupamento,
                "code_prefix": str(o.code_prefix),
                # Honor the recorded status: a re-orphaned, already-purged code reads
                # 'purged', not a hardcoded 'descontinuado'. None until the marker runs.
                "status": (st.status if st is not None else "descontinuado"),
                "flagged_at": str(st.flagged_at) if st is not None else None,
                # 'purged' events carry no purge note → fall back to the standing warning.
                "warning": (
                    st.scheduled_purge_note
                    if (st is not None and st.scheduled_purge_note)
                    else PURGE_WARNING
                ),
            }
        )
    return {"orphans": rows, "total": len(rows)}
