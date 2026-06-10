"""IAP author capture for the REST layer.

The dashboard runs behind Identity-Aware Proxy (direct Cloud Run IAP). Read-only
endpoints don't need the identity — IAP already gated the request. The curation
WRITE endpoint does: it records ``edited_by`` in the append-only audit log, so the
author must come from the IAP-verified header (the signed JWT when ``iap_audience``
is configured; the plaintext header + ``curation_dev_author`` fallback in local
dev). This is a thin wrapper over the already-tested ``serving.iap`` logic.
"""

from __future__ import annotations

from flask import request

from embrapa_commodities.config import get_settings
from embrapa_commodities.serving.iap import author_email_from_headers


def current_author() -> str:
    """Resolve the editing researcher's email from the current request's IAP
    headers. Raises ``MissingAuthorError`` / ``InvalidIapAssertionError`` (both
    ``PermissionError`` subclasses) when no trustworthy identity is present —
    callers map those to HTTP 401/403."""
    cfg = get_settings()
    return author_email_from_headers(
        request.headers,
        dev_fallback=cfg.curation_dev_author,
        audience=cfg.iap_audience,
    )
