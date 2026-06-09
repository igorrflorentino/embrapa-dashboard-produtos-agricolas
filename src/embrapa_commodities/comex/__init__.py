"""MDIC Comex Stat (foreign trade) source package.

Bulk-CSV ingestion of Brazilian foreign-trade flows (export + import) into the
``gold_comex_flows`` lineage. Unlike IBGE/BCB this source is a plain CSV
downloader, not a JSON API: the authoritative base is the per-year
``EXP_<year>.csv`` / ``IMP_<year>.csv`` files published by the MDIC. See
``PLANS/comex_flows.md`` for the rationale (the JSON API silently returned the
aggregated Brazil total on a malformed filter, HTTP 200 — unsafe to ingest).
"""
