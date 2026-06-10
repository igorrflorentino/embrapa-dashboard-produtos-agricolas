"""webapi — the REST layer between the React SPA and the serving BFF.

Replaces the Dash UI's in-process seam calls with HTTP: the SPA (frontend/,
the design-system prototype reused verbatim) fetches JSON from ``/api/*``;
every endpoint wraps an existing seam/gateway function and serializes to the
exact shapes the prototype's ``contracts.js`` defines. Same Pushdown model —
parameterized BigQuery via ``serving.gateway``, memoized by flask-caching —
only the transport changes (in-process → JSON over HTTP, IAP in front).

NOTE: until the Dash package is removed (migration task 8), the data seam is
imported from ``embrapa_commodities.dashboard`` (seam/format/registries are
UI-framework-free modules there); they relocate here when Dash is deleted.
"""
