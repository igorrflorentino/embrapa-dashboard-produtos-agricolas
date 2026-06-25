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
            "agrupamento": r.agrupamento,
            "descricao_commodity": r.descricao_commodity,
            "industrializacao": r.industrializacao,
            "ciclo_de_vida": r.ciclo_de_vida,
            "code_prefix": str(r.code_prefix),
            "commodity_id": r.commodity_id,
        }
        for r in df.itertuples()
    ]
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
        industrializacao=payload.get("industrializacao"),
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
                "status": "descontinuado",
                "flagged_at": str(st.flagged_at) if st is not None else None,
                "warning": (st.scheduled_purge_note if st is not None else PURGE_WARNING),
            }
        )
    return {"orphans": rows, "total": len(rows)}
