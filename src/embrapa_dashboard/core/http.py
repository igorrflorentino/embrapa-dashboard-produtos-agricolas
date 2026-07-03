"""Shared HTTP primitives for source clients (Bronze layer).

The resilience patterns common to every external API client live here:
the tenacity retry policy and the manual-drain slow-byte defense. Each
source's ``client.py`` composes them with its own deadlines, transient
exception class, and status-handling logic.

Contract for ``transient_exc`` parameters: must derive from
:class:`embrapa_dashboard.core.SourceTransientError` so cross-source
code can catch retryable failures uniformly without listing each subclass.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_random_exponential,
)

# (connect_timeout, read_timeout). 30s read is the per-chunk byte-idle
# deadline. Combined with the per-call total deadline passed to
# ``get_drained`` this caps total time spent on a single HTTP request —
# slow-byte hangs can't strand a worker thread.
DEFAULT_TIMEOUT: tuple[float, float] = (10.0, 30.0)

# Connection: close forces a new TCP socket per request — slower handshake
# but avoids both urllib3 pool deadlocks and server-side staleness observed
# against SIDRA and BCB. ``get_drained``'s close-on-abort behaviour also
# assumes this: see docstring.
DEFAULT_HEADERS: dict[str, str] = {
    "Connection": "close",
    "User-Agent": "embrapa-dashboard/0.1",
}

# Status codes worth retrying — transient/server-side or rate limits.
# 4xx other than these (400, 401, 403, 404...) won't recover by retrying.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


def http_retry_policy(
    *,
    transient_exc: type[BaseException],
    deadline_s: float,
    max_attempts: int = 5,
    before_sleep: Callable[[Any], None] | None = None,
):
    """tenacity ``@retry`` factory for HTTP source clients.

    Stops on EITHER ``max_attempts`` OR cumulative ``deadline_s`` —
    whichever fires first. The OR matters: a slow-byte hang shouldn't
    keep the worker alive past the deadline even if it never exhausts
    attempts. Retries on ``requests.RequestException`` or ``transient_exc``.

    Backoff is FULL-JITTER exponential (``wait_random_exponential``): each
    sleep is ``uniform(0, min(60, 2**attempt))`` rather than a fixed
    ``2,4,8…`` ramp. The jitter de-synchronises retries across the parallel
    state-fetch workers (IBGE runs up to 4 at once), so a brief upstream
    slowdown doesn't make all workers re-hit SIDRA in lockstep — the
    thundering-herd that turns a transient slow patch into a sustained one.

    ``before_sleep`` is forwarded verbatim — callers inject their own
    observability hook (e.g. IBGE's ``_emit_retry`` reading a contextvar);
    pass ``None`` to opt out.
    """
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts) | stop_after_delay(deadline_s),
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=retry_if_exception_type((requests.RequestException, transient_exc)),
        before_sleep=before_sleep,
    )


def get_drained(
    url: str,
    *,
    total_deadline_s: float,
    transient_exc: type[BaseException],
    context: str = "",
    timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET with ``stream=True`` + manual body drain under a wall-clock deadline.

    Returns a :class:`requests.Response` with its body already in
    ``response._content`` (and ``_content_consumed=True``) so the caller's
    ``response.json()`` / ``response.text`` work without re-reading the
    network. **Both** private attrs are required: setting only ``_content``
    is not enough — the next ``.text`` access would still try to drain
    the (already closed) stream and raise.

    On wall-clock deadline exceeded mid-drain, raises ``transient_exc``
    with a message of the form
    ``"HTTP request exceeded {n}s total budget (slow-byte hang) for {ctx}"``
    where ``ctx`` is the ``context`` argument (or ``url[:200]`` if empty).
    The format is preserved from the original IBGE/BCB clients so existing
    tests that match on ``"slow-byte hang"`` still pass.

    Preconditions:

    - ``transient_exc`` should derive from
      :class:`embrapa_dashboard.core.SourceTransientError` (see module
      docstring) so a shared retry policy can catch it.
    - The default headers include ``Connection: close``; on a slow-byte
      abort, the underlying socket is closed without finishing the drain
      and would otherwise be returned to the pool in a dirty state. If
      a caller overrides headers without ``Connection: close``, that
      pathway becomes suboptimal.

    On success, returns the Response without closing it — the caller owns
    its lifetime (the body is already in memory, so a later ``close()``
    keeps ``.text`` / ``.json()`` working). On any exception during the
    drain, the Response is closed before re-raising.
    """
    # Copy defensively so a caller mutating the returned dict (or future
    # code mutating module-level DEFAULT_HEADERS) doesn't poison subsequent
    # requests.
    headers = dict(headers) if headers is not None else dict(DEFAULT_HEADERS)
    deadline = time.monotonic() + total_deadline_s
    response = requests.get(url, timeout=timeout, headers=headers, stream=True)
    try:
        # Drain the body manually so we can enforce a total wall-clock budget.
        # Done for both happy and error paths so the same slow-byte defense
        # applies to error responses (SIDRA and BCB both sometimes trickle
        # error bodies).
        buf = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if time.monotonic() > deadline:
                raise transient_exc(
                    f"HTTP request exceeded {total_deadline_s}s total budget "
                    f"(slow-byte hang) for {context or url[:200]}"
                )
            if chunk:
                buf.extend(chunk)
        # Stash the drained body so the caller's response.json() and
        # response.text work without re-reading from the network. Private
        # attrs of requests.Response, but the names are stable across
        # versions and required together (see docstring).
        response._content = bytes(buf)  # type: ignore[attr-defined]
        response._content_consumed = True  # type: ignore[attr-defined]
        return response
    except BaseException:
        # Ensure the underlying socket is released on any exit other than
        # the happy-path return above.
        response.close()
        raise
