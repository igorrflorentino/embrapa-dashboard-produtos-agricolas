"""``/api`` blueprint — thin REST wrappers over the serving BFF seam.

Each endpoint wraps an existing ``seam`` function and serializes to the exact
shape the prototype's ``contracts.js`` defines (the React data layer fetches
these instead of computing synthetically). Same Pushdown model underneath.

STATUS: the catalog + source-meta endpoints (clean dicts, no reshape) are wired;
the snapshot / cross-analytics / curation endpoints — which need the precise
field-by-field DataFrame→contracts.js mapping — land per
``PLANS/react_migration_contract_map.md``.

NOTE: ``seam`` lives in the (UI-framework-free) ``dashboard`` package until the
Dash UI is deleted; it relocates under ``webapi`` then.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from embrapa_commodities.dashboard import seam

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


@api.get("/catalog")
def catalog():
    """Crosswalk commodity catalog (commodity_id → {name, pevs[], comex[], comtrade[]})."""
    return jsonify(seam.commodity_catalog())


@api.get("/source-meta")
def source_meta():
    """Provenance row for a banco (backs the page-hero meta); {} if absent."""
    return jsonify(seam.source_meta(request.args.get("banco", "")))
