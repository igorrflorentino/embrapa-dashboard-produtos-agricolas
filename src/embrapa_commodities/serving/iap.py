"""Parse the author identity injected by Identity-Aware Proxy (IAP).

When the dashboard runs behind IAP, every request carries the verified end-user
identity in the ``X-Goog-Authenticated-User-Email`` header, formatted as
``accounts.google.com:user@example.com``. The curation writer records the email
in the ``edited_by`` audit column, so a manual reclassification is always
attributable to a real person — never to the dashboard's service account.

Pure module: no Flask or BigQuery imports, so it is trivially unit-testable.
"""

from __future__ import annotations

from collections.abc import Mapping

# IAP sets both; we want the email. The value is "<issuer>:<email>".
IAP_EMAIL_HEADER = "X-Goog-Authenticated-User-Email"


class MissingAuthorError(PermissionError):
    """Raised when no IAP author email is present and no dev fallback is set.

    In production this should never happen: IAP guarantees the header on every
    request. It surfaces as a hard error precisely so a misconfigured proxy
    cannot silently write an un-attributed row to the audit log.
    """


def author_email_from_headers(
    headers: Mapping[str, str],
    *,
    dev_fallback: str | None = None,
) -> str:
    """Extract the verified author email from request headers.

    ``headers`` may be a Flask/Werkzeug ``request.headers`` (case-insensitive)
    or a plain dict. Strips the ``<issuer>:`` prefix IAP prepends. Falls back to
    ``dev_fallback`` (e.g. for local development without IAP) only when provided;
    otherwise raises :class:`MissingAuthorError`.
    """
    raw = _get_header(headers, IAP_EMAIL_HEADER)
    if raw:
        # "accounts.google.com:user@example.com" -> "user@example.com".
        # An email never contains a colon, so splitting on the first one is safe.
        email = raw.split(":", 1)[-1].strip() if ":" in raw else raw.strip()
        if email:
            return email

    if dev_fallback:
        return dev_fallback

    raise MissingAuthorError(
        f"No {IAP_EMAIL_HEADER} header and no curation_dev_author fallback configured. "
        "Refusing to write an un-attributed curation row."
    )


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup that works on dicts and Werkzeug headers."""
    getter = getattr(headers, "get", None)
    if getter is not None:
        value = getter(name)
        if value:
            return value
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None
