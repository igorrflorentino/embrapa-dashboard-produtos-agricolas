"""webapi — the REST layer between the React SPA and the serving BFF.

The SPA (``frontend/``, the design-system prototype reused verbatim) fetches JSON
from ``/api/*``; every endpoint wraps a ``seam``/``gateway`` function and
serializes to the exact shapes the prototype's ``contracts.js`` defines. Same
Pushdown model — parameterized BigQuery via ``serving.gateway``, memoized by
flask-caching — only the transport is JSON over HTTP, with IAP in front.

This package owns the UI-framework-free data composition layer that used to live
under the (now-removed) Dash package: ``seam`` (composes the gateway readers into
the contract shapes), ``format`` (pt-BR formatting + convention→column mapping),
and ``registries`` (banco/metric/view registries).
"""
