"""Data-access layer for the stateless dashboard backend (Pushdown Computing).

This package is the UI-agnostic backend the webapi (Flask app factory + React
SPA) imports. It does NOT contain any pages, layouts, or chart components — the
React frontend lives in ``frontend/`` and the REST host in
``embrapa_dashboard.webapi``. What lives here is the data seam:

* ``sql``       — pure, parameterized BigQuery SQL builders (no I/O).
* ``iap``       — pure parsing of the IAP-injected author email header.
* ``cache``     — the ``flask-caching`` instance + ``init_cache`` wiring.
* ``gateway``   — cached, parameterized reads against the ``serving`` marts.
* ``curation``  — the append-only curation writers behind the editor's "Save".

Architecture: the backend is stateless. It never loads a Gold table into a
Pandas DataFrame held behind a global lock; instead it translates UI filters
into ``@param`` queries that BigQuery executes against the pre-aggregated
``serving`` marts, and caches the small result sets with ``flask-caching``.

Requires the optional ``serving`` extra (``flask`` + ``flask-caching``); the
ingestion CLI never imports this package.
"""

from __future__ import annotations
