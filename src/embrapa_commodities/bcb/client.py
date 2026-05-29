"""HTTP client for the Banco Central do Brasil SGS API."""

from __future__ import annotations

import logging

import pandas as pd

from embrapa_commodities.core import SourceTransientError
from embrapa_commodities.core import http as core_http

logger = logging.getLogger(__name__)

SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)
# (connect_timeout, read_timeout). Same per-chunk byte-idle deadline as IBGE.
REQUEST_TIMEOUT: tuple[float, float] = (10.0, 30.0)
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


@core_http.http_retry_policy(
    transient_exc=BcbTransientError,
    # Stop on either attempt count OR cumulative time — same pattern as IBGE.
    deadline_s=PER_SERIES_DEADLINE_S,
    # before_sleep deliberately omitted — preserves the pre-D1 behaviour.
    # Symmetric observability with IBGE's `_emit_retry` is tracked as D1.1.
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
