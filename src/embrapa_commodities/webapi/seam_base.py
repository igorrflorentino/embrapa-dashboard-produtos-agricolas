"""Shared primitives for the seam layer.

Low-level helpers used by BOTH the cross-source analytics (``seam_cross``) and the
attribute-engineering readers (``seam_attribute_engineering``): the live-source set
and the commodity crosswalk toolkit (catalog, per-source code lookup, per-metric
yearly points). Kept in their own module so the two analytic modules depend only on
this base — never on each other or on ``seam`` — which keeps the import graph a clean
DAG (base ← {cross, attributes} ← seam) with no cycles. ``seam`` re-exports these so
``seam.commodity_catalog`` / ``seam._xyear`` etc. stay available to callers + tests.

The crosswalk/catalog reads are memoized with the SAME flask-caching TTL the
gateway mart reads use (CACHE_DEFAULT_TIMEOUT) — NOT functools.lru_cache: the
crosswalk and the Gold families it joins are rebuilt by the nightly dbt run, so a
long-lived Cloud Run instance must converge to the fresh catalog within the TTL
instead of serving a stale one for its whole process lifetime.
"""

from __future__ import annotations

import pandas as pd

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving import gateway
from embrapa_commodities.serving import sql as sqlbuild
from embrapa_commodities.serving.cache import cache

# Banco id → the BFF source key (they already align by construction).
_LIVE_SOURCES = {"ibge_pevs", "ibge_pam", "ibge_ppm", "mdic_comex", "un_comtrade"}


@cache.memoize()
def _crosswalk_df() -> pd.DataFrame:
    # F7 visibility gate: exclude commodities a researcher marked "indisponível" so the
    # cross-source picker AGREES with the (gated) per-banco pickers. Same single source of
    # truth as the dbt marts + gateway readers — dim_commodity_visibility — never re-derived
    # in Python. gold_commodity_crosswalk.source is already the short token (pevs/comex/
    # comtrade), matching the view. A no-op today (nothing hidden); the admin/orphan readers
    # are intentionally NOT gated (they must still see hidden-but-active rows).
    s = get_settings()
    fqn = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_commodity_crosswalk")
    vis = sqlbuild.table_ref(s, "bq_gold_dataset", "dim_commodity_visibility")
    sql = (
        f"select x.commodity_id, x.commodity_name, x.source, x.code from `{fqn}` x "
        f"where not exists (select 1 from `{vis}` v "
        f"where v.source = x.source and x.code = v.code)"
    )
    return gateway.run_query(sql, [])


@cache.memoize()
def commodity_catalog() -> dict:
    """commodity_id -> {id, name, pevs[], comex[], comtrade[]} from the crosswalk."""
    cat: dict = {}
    for r in _crosswalk_df().itertuples():
        c = cat.setdefault(
            r.commodity_id,
            {
                "id": r.commodity_id,
                "name": r.commodity_name,
                "pevs": [],
                "comex": [],
                "comtrade": [],
            },
        )
        c[r.source].append(str(r.code))
    return cat


def _codes(commodity_id: str | None, source: str) -> tuple:
    c = commodity_catalog().get(commodity_id) if commodity_id else None
    return tuple(c[source]) if c else ()


def _xyear(metric: str, codes: tuple, uf_codes: tuple = ()) -> dict:
    """{year: raw value} from the gateway cross reader for a metric, scoped to codes.

    ``uf_codes`` optionally narrows to origin UFs (cross-source per-UF scoping); it
    only affects COMEX metrics — the gateway drops it for COMTRADE (no UF column)."""
    df = gateway.fetch_cross_series(metric, codes=codes, uf_codes=uf_codes)
    return {int(r.reference_year): float(r.value or 0) for r in df.itertuples()}
