"""Shared primitives for the seam layer.

Low-level helpers used by BOTH the cross-source analytics (``seam_cross``) and the
curation/enrichment readers (``seam_curation``): the live-source set and the
commodity crosswalk toolkit (catalog, per-source code lookup, per-metric yearly
points). Kept in their own module so the two analytic modules depend only on this
base — never on each other or on ``seam`` — which keeps the import graph a clean
DAG (base ← {cross, curation} ← seam) with no cycles. ``seam`` re-exports these so
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
_LIVE_SOURCES = {"ibge_pevs", "ibge_pam", "mdic_comex", "un_comtrade"}


@cache.memoize()
def _crosswalk_df() -> pd.DataFrame:
    s = get_settings()
    fqn = sqlbuild.table_ref(s, "bq_gold_dataset", "gold_commodity_crosswalk")
    return gateway.run_query(f"select commodity_id, commodity_name, source, code from `{fqn}`", [])


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


def _xyear(metric: str, codes: tuple) -> dict:
    """{year: raw value} from the gateway cross reader for a metric, scoped to codes."""
    df = gateway.fetch_cross_series(metric, codes=codes)
    return {int(r.reference_year): float(r.value or 0) for r in df.itertuples()}
