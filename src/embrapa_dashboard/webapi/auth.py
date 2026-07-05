"""IAP author capture for the REST layer.

The dashboard runs behind Identity-Aware Proxy (direct Cloud Run IAP). Read-only
endpoints don't need the identity — IAP already gated the request. The curation
WRITE endpoint does: it records ``edited_by`` in the append-only audit log, so the
author must come from the IAP-verified header (the signed JWT when ``iap_audience``
is configured; the plaintext header + ``dev_author`` fallback in local
dev). This is a thin wrapper over the already-tested ``serving.iap`` logic.
"""

from __future__ import annotations

import os

from flask import request

from embrapa_dashboard.config import get_settings
from embrapa_dashboard.serving.iap import InvalidIapAssertionError, author_email_from_headers


def current_author() -> str:
    """Resolve the editing researcher's email from the current request's IAP
    headers. Raises ``MissingAuthorError`` / ``InvalidIapAssertionError`` (both
    ``PermissionError`` subclasses) when no trustworthy identity is present —
    callers map those to HTTP 401/403."""
    cfg = get_settings()
    # Fail CLOSED in production. On Cloud Run (``K_SERVICE`` is set by the runtime)
    # the curation author is stamped into an immutable audit log, so it must come
    # from the cryptographically verified IAP JWT — which requires ``iap_audience``.
    # With it unset, ``author_email_from_headers`` would silently fall back to the
    # spoofable plaintext ``X-Goog-Authenticated-User-Email`` header, so refuse to
    # record a forgeable identity rather than trust it. (Local dev has no K_SERVICE,
    # so the ``dev_author`` fallback still works there.) This is the one
    # defense that holds regardless of the platform IAP/IAM ingress posture.
    if os.environ.get("K_SERVICE") and not cfg.iap_audience:
        raise InvalidIapAssertionError(
            "Refusing to capture a curation author on Cloud Run without IAP_AUDIENCE: "
            "the in-app IAP JWT verification is disarmed, so the plaintext "
            "X-Goog-Authenticated-User-Email header is forgeable. Set IAP_AUDIENCE."
        )
    return author_email_from_headers(
        request.headers,
        dev_fallback=cfg.dev_author,
        audience=cfg.iap_audience,
    )
