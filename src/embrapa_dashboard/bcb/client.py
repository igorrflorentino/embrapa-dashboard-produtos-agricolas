"""HTTP client for the Banco Central do Brasil SGS API."""

from __future__ import annotations

import logging

import pandas as pd

from embrapa_dashboard import observability
from embrapa_dashboard.core import SourceTransientError
from embrapa_dashboard.core import http as core_http

logger = logging.getLogger(__name__)

SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)
# The (connect, read) timeout for the actual GET lives in
# ``core_http.DEFAULT_TIMEOUT`` — see ``_fetch_window`` -> ``core_http.get_drained``.
# Hard wall-clock ceiling for one HTTP request. Mirrors the IBGE client: the
# per-read timeout only fires on full byte-idle gaps, so a server that trickles
# 1 byte every ~29s could bypass it forever. We drain the body manually with
# this deadline to escape that pathology.
REQUEST_TOTAL_DEADLINE_S: float = 60.0
# Hard ceiling across all retries for one series window — prevents a single
# stalled series from blocking the whole inflation/currency ingest.
PER_SERIES_DEADLINE_S: float = 120.0


class BcbRequestError(Exception):
    """Non-200 response from the BCB SGS API (base class)."""


class BcbTransientError(BcbRequestError, SourceTransientError):
    """Transient (retryable) response from the BCB SGS API."""


# BCB SGS occasionally truncates payloads silently when the window is too wide.
# Chunking caps each HTTP call to a known-safe range and concatenates results.
MAX_YEARS_PER_REQUEST = 10


def _emit_retry(retry_state):  # type: ignore[no-untyped-def]
    """Tenacity before_sleep hook: emit a structured retry event + warn.

    Mirrors the IBGE client's hook so BCB retries also surface in
    ``embrapa monitor``. Unlike IBGE — where the observable unit (the UF) lives
    one frame up in ``_fetch_one_state`` and needs a contextvar — the retried
    function here IS ``_fetch_window``, so the (code, window) context comes
    straight off the call args carried on ``retry_state``.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    args = retry_state.args
    kwargs = retry_state.kwargs
    code = args[0] if len(args) > 0 else kwargs.get("code", "?")
    start = args[1] if len(args) > 1 else kwargs.get("start_year", "?")
    end = args[2] if len(args) > 2 else kwargs.get("end_year", "?")
    observability.emit(
        "retry",
        series=code,
        window=f"{start}-{end}",
        attempt=retry_state.attempt_number,
        reason=str(exc)[:200] if exc else "?",
    )
    logger.warning(
        "Retrying BCB SGS fetch code=%s window=%s-%s attempt=%d: %s",
        code,
        start,
        end,
        retry_state.attempt_number,
        exc,
    )


@core_http.http_retry_policy(
    transient_exc=BcbTransientError,
    # Stop on either attempt count OR cumulative time — same pattern as IBGE.
    deadline_s=PER_SERIES_DEADLINE_S,
    before_sleep=_emit_retry,
)
def _fetch_window(code: str, start_year: int, end_year: int) -> pd.DataFrame:
    """One atomic HTTP call to SGS. Empty payload → empty DataFrame."""
    url = SGS_URL.format(
        code=code,
        start=f"01/01/{start_year}",
        end=f"31/12/{end_year}",
    )
    logger.info("BCB SGS fetch code=%s window=%d-%d", code, start_year, end_year)
    # The drain-under-deadline + Connection: close + slow-byte defense live in
    # ``core_http.get_drained``. Year-chunking stays in ``fetch_series`` below
    # so the helper doesn't grow API knowledge.
    response = core_http.get_drained(
        url,
        total_deadline_s=REQUEST_TOTAL_DEADLINE_S,
        transient_exc=BcbTransientError,
        context=f"SGS {code} {start_year}-{end_year}",
    )
    try:
        if response.status_code != 200:
            # BCB SGS answers 404 when a (valid) series simply has no
            # observations in the requested window — e.g. EUR before 1999.
            # Treat it as "no data", not an error, so a --full from
            # BCB_START_YEAR works for series with different inception dates
            # (the year-chunking in ``fetch_series`` queries early windows that
            # predate some series). A genuinely bad series code also 404s and
            # yields empty here, which the full-mode per-series empty guard in
            # ``series.extract`` catches (it raises naming the empty series).
            if response.status_code == 404:
                logger.info(
                    "BCB SGS %s: 404 (no data) for %d-%d — skipping window.",
                    code,
                    start_year,
                    end_year,
                )
                return pd.DataFrame(columns=["data", "valor"])
            msg = f"HTTP {response.status_code} for SGS {code}: {response.text[:200]}"
            if response.status_code in core_http.RETRYABLE_STATUS_CODES:
                raise BcbTransientError(msg)
            raise BcbRequestError(msg)

        payload = response.json()
        if not payload:
            logger.warning("BCB SGS %s returned no rows for %d-%d", code, start_year, end_year)
            return pd.DataFrame(columns=["data", "valor"])
        return pd.DataFrame(payload)
    except BaseException:
        # ``get_drained`` already closes on its own exceptions; this guards
        # the status-check branch.
        response.close()
        raise


def fetch_series(code: str, start_year: int, end_year: int) -> pd.DataFrame:
    """Fetch one SGS series, automatically chunking windows > MAX_YEARS_PER_REQUEST."""
    if end_year - start_year + 1 <= MAX_YEARS_PER_REQUEST:
        return _fetch_window(code, start_year, end_year)

    frames: list[pd.DataFrame] = []
    for chunk_start in range(start_year, end_year + 1, MAX_YEARS_PER_REQUEST):
        chunk_end = min(chunk_start + MAX_YEARS_PER_REQUEST - 1, end_year)
        df = _fetch_window(code, chunk_start, chunk_end)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["data", "valor"])
    return pd.concat(frames, ignore_index=True)
