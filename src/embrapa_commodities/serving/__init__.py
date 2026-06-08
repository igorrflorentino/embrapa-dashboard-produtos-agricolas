"""Data-access layer for the stateless Dash dashboard (Pushdown Computing).

This package is the UI-agnostic backend the dashboard imports. It does NOT
contain any Dash pages, layouts, or chart components — those arrive with the
Claude Design System handoff. What lives here is the data seam:

* ``sql``       — pure, parameterized BigQuery SQL builders (no I/O).
* ``iap``       — pure parsing of the IAP-injected author email header.
* ``cache``     — the ``flask-caching`` instance + ``init_cache`` wiring.
* ``gateway``   — cached, parameterized reads against the ``serving`` marts.
* ``curation``  — the append-only SCD2 writer triggered by the "Save" button.

Architecture: the dashboard is stateless. It never loads a Gold table into a
Pandas DataFrame held behind a global lock; instead it translates UI filters
into ``@param`` queries that BigQuery executes against the pre-aggregated
``serving`` marts, and caches the small result sets with ``flask-caching``.

Requires the optional ``serving`` extra (``flask`` + ``flask-caching``); the
ingestion CLI never imports this package.
"""

from __future__ import annotations
