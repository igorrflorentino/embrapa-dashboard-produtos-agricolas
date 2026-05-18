"""HTTP client for the Banco Central do Brasil SGS API."""

from __future__ import annotations

import logging

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)
REQUEST_TIMEOUT = 60

# Status codes worth retrying — transient/server-side or rate limits.
# 4xx other than these (400, 401, 403, 404...) won't recover by retrying.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


class BcbRequestError(Exception):
    """Non-200 response from the BCB SGS API (base class)."""


class BcbTransientError(BcbRequestError):
    """Transient (retryable) response from the BCB SGS API."""


# BCB SGS occasionally truncates payloads silently when the window is too wide.
# Chunking caps each HTTP call to a known-safe range and concatenates results.
MAX_YEARS_PER_REQUEST = 10


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException, BcbTransientError)),
)
def _fetch_window(code: str, start_year: int, end_year: int) -> pd.DataFrame:
    """One atomic HTTP call to SGS. Empty payload → empty DataFrame."""
    url = SGS_URL.format(
        code=code,
        start=f"01/01/{start_year}",
        end=f"31/12/{end_year}",
    )
    logger.info("BCB SGS fetch code=%s window=%d-%d", code, start_year, end_year)
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 200:
        payload = response.json()
        if not payload:
            logger.warning("BCB SGS %s returned no rows for %d-%d", code, start_year, end_year)
            return pd.DataFrame(columns=["data", "valor"])
        return pd.DataFrame(payload)

    msg = f"HTTP {response.status_code} for SGS {code}: {response.text[:200]}"
    if response.status_code in RETRYABLE_STATUS_CODES:
        raise BcbTransientError(msg)
    raise BcbRequestError(msg)


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
