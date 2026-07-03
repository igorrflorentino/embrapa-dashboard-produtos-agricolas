"""Parse (and cryptographically verify) the author identity injected by IAP.

When the dashboard runs behind Identity-Aware Proxy (IAP), every request carries
the verified end-user identity in two forms:

* ``X-Goog-Authenticated-User-Email`` — a convenience header, plaintext, of the
  form ``accounts.google.com:user@example.com``. Trivial to *read* but **forgeable**
  by any client that can reach the backend directly (i.e. only when IAP is not in
  front — local dev; in prod Cloud Run direct IAP overwrites it with the verified
  identity).
* ``X-Goog-IAP-JWT-Assertion`` — a **signed** JWT IAP mints with its private key.
  Validating its signature against Google's public certs (and checking the
  ``aud`` claim matches *this* backend) is the only spoof-proof way to learn who
  the caller is.

The curation writer records the email in the ``edited_by`` audit column of an
append-only log, so a forged identity would permanently mis-attribute an edit.
In production (``iap_audience`` set) we therefore derive the author from the
*verified JWT*, falling back to the plaintext header only for local dev where no
IAP sits in front and no audience is configured.

Pure module: the JWT verification calls google-auth (already a dependency) but
performs no project-specific I/O, so it is unit-testable by mocking that one call.
"""

from __future__ import annotations

from collections.abc import Mapping

# IAP sets both; we want the email. The value is "<issuer>:<email>".
IAP_EMAIL_HEADER = "X-Goog-Authenticated-User-Email"
# IAP's signed assertion — the spoof-proof identity. Verified against Google's
# published public keys; its 'email' claim is the trustworthy author.
IAP_JWT_HEADER = "X-Goog-IAP-JWT-Assertion"
# Google's IAP public-key endpoint (JWKS-equivalent) used to verify the assertion.
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
# The only issuer a genuine IAP assertion carries. google-auth verifies the
# signature + audience + expiry but does NOT check `iss`, so we assert it here.
IAP_ISSUER = "https://cloud.google.com/iap"


class MissingAuthorError(PermissionError):
    """Raised when no IAP author email is present and no dev fallback is set.

    In production this should never happen: IAP guarantees the header on every
    request. It surfaces as a hard error precisely so a misconfigured proxy
    cannot silently write an un-attributed row to the audit log.
    """


class InvalidIapAssertionError(PermissionError):
    """Raised when an audience is configured but the signed IAP JWT fails to verify.

    Covers a missing, malformed, expired, wrong-audience, or wrong-issuer
    ``X-Goog-IAP-JWT-Assertion``. Surfaces as a hard error so a forged or absent
    assertion can never reach the audit log under the plaintext (spoofable) header.
    """


def verify_iap_jwt(
    headers: Mapping[str, str],
    *,
    audience: str,
    certs_url: str = IAP_CERTS_URL,
) -> str:
    """Cryptographically verify the IAP assertion and return its ``email`` claim.

    Validates the ``X-Goog-IAP-JWT-Assertion`` signature against Google's IAP
    public keys (``certs_url``) and checks the token's ``aud`` claim equals
    ``audience`` (the expected backend — with the prod posture, Cloud Run direct
    IAP, this is the Cloud-Run-resource audience code; only the future external-LB
    topology would use ``/projects/<PROJ_NUM>/global/backendServices/<SVC_ID>``).
    Returns the verified end-user email. Raises :class:`InvalidIapAssertionError` on any
    failure (missing header, bad signature, expired, wrong audience/issuer, or a
    token without an ``email`` claim) — never falls through to the plaintext header.

    Pure-ish: the only outbound call is google-auth fetching/caching Google's
    public certs; no project state is touched, so tests mock ``verify_token``.
    """
    from google.auth.transport import requests as ga_requests
    from google.oauth2 import id_token

    token = _get_header(headers, IAP_JWT_HEADER)
    if not token:
        raise InvalidIapAssertionError(
            f"Missing {IAP_JWT_HEADER}; refusing to trust the plaintext "
            f"{IAP_EMAIL_HEADER} when an IAP audience is configured."
        )
    try:
        claims = id_token.verify_token(
            token,
            ga_requests.Request(),
            audience=audience,
            certs_url=certs_url,
        )
    except Exception as exc:  # google-auth raises ValueError subclasses on any failure
        raise InvalidIapAssertionError(f"IAP JWT assertion failed to verify: {exc}") from exc

    # verify_token checks signature/aud/exp but NOT the issuer — assert it so a
    # validly-signed token minted for a different Google product can't be replayed.
    issuer = (claims or {}).get("iss", "")
    if issuer != IAP_ISSUER:
        raise InvalidIapAssertionError(
            f"IAP JWT has unexpected issuer {issuer!r} (expected {IAP_ISSUER!r})."
        )

    email = (claims or {}).get("email", "").strip()
    if not email:
        raise InvalidIapAssertionError("Verified IAP JWT has no 'email' claim.")
    return email


def author_email_from_headers(
    headers: Mapping[str, str],
    *,
    dev_fallback: str | None = None,
    audience: str | None = None,
) -> str:
    """Extract the author email from request headers, preferring the verified JWT.

    ``headers`` may be a Flask/Werkzeug ``request.headers`` (case-insensitive) or a
    plain dict.

    * When ``audience`` is set (production behind IAP), the email comes from the
      cryptographically verified ``X-Goog-IAP-JWT-Assertion`` via
      :func:`verify_iap_jwt`. A spoofed plaintext header cannot win, and a
      missing/invalid assertion raises :class:`InvalidIapAssertionError`.
    * When ``audience`` is ``None`` (local dev with no IAP), it reads the plaintext
      ``X-Goog-Authenticated-User-Email`` header (stripping the ``<issuer>:``
      prefix), falling back to ``dev_fallback`` if provided, else raising
      :class:`MissingAuthorError`.

    Backward-compatible: the original ``(headers, *, dev_fallback)`` signature is
    unchanged; ``audience`` is a new opt-in keyword.
    """
    if audience:
        return verify_iap_jwt(headers, audience=audience)

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
