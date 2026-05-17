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


class BcbRequestError(Exception):
    """Non-200 (and non-empty) response from the BCB SGS API."""


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException, BcbRequestError)),
)
def fetch_series(code: str, start_year: int, end_year: int) -> pd.DataFrame:
    """Fetch one SGS series as a raw DataFrame with columns [data, valor]."""
    url = SGS_URL.format(
        code=code,
        start=f"01/01/{start_year}",
        end=f"31/12/{end_year}",
    )
    logger.info("BCB SGS fetch code=%s window=%d-%d", code, start_year, end_year)
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        raise BcbRequestError(f"HTTP {response.status_code} for SGS {code}: {response.text[:200]}")
    payload = response.json()
    if not payload:
        logger.warning("BCB SGS %s returned no rows for %d-%d", code, start_year, end_year)
        return pd.DataFrame(columns=["data", "valor"])
    return pd.DataFrame(payload)
