"""Analytical perspectives — one ``layout(banco_id, conv, summary)`` per view.

Each builder reads the serving snapshot via ``seam`` and returns the view body
(KPI row + card grids); the router (``app``) wraps it with the page hero and the
maturity caveat banner, mirroring the prototype's ``MainScreen``.
"""

from __future__ import annotations
