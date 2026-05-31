"""UN Comtrade (global trade) source package.

Keyed JSON API ingestion of worldwide bilateral trade flows into the
``gold_comtrade_flows`` lineage — the global complement to Brazil-only COMEX.
See ``PLANS/comtrade_flows.md``. The free subscription key (``COMTRADE_API_KEY``)
raises the per-call record limit from 500 (keyless preview) to ~100k; the daily
call quota is absorbed by the resumable two-phase raw zone (stop on quota, pick
up the un-archived chunks next run).
"""
