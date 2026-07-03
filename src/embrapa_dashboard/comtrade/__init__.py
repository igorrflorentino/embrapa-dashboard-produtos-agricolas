"""UN Comtrade (global trade) source package.

Keyed JSON API ingestion of worldwide bilateral trade flows into the
``gold_comtrade_flows`` lineage — the global complement to Brazil-only COMEX.
See ``PLANS/comtrade_flows.md``. The free subscription key (``COMTRADE_API_KEY``)
raises the per-call record limit from 500 (keyless preview) to ~100k; the daily
call quota is absorbed by the resumable two-phase raw zone.

**Stop on quota.** A keyed data call that 429s means the daily budget is spent;
the client raises a non-retryable ``ComtradeQuotaError`` and ``pipeline.run``
breaks its chunk loop at once rather than burning the remaining budget on
retries. Re-running later resumes from exactly the un-archived chunks — no lost
work, no duplication beyond what Silver dedupes.
"""
