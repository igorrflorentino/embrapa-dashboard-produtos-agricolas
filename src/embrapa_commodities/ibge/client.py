"""HTTP client for the IBGE SIDRA values endpoint with adaptive slicing."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# All 27 Brazilian federative units (IBGE n3 codes).
BRAZIL_STATES: tuple[int, ...] = (
    11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53,
)

SIDRA_VALUES_URL = "https://apisidra.ibge.gov.br/values/t/{table_id}/p/{periods}/v/all/{geo_level}/{geo_filter}/c{classification}/{products}"

# (connect_timeout, read_timeout). `read_timeout` is per-chunk, not total —
# but with SIDRA's chunked responses for large payloads, 180s is enough margin.
# Observed: a 2-year, 3-product, all-municipalities payload (~17 MB) takes
# ~60s on a typical connection.
REQUEST_TIMEOUT: tuple[float, float] = (10.0, 180.0)

# Concurrent state-level requests. 4 workers is the sweet spot for SIDRA: 8+
# can deadlock urllib3's internal connection pool when SIDRA closes idle
# sockets server-side, while 4 still cuts wall-clock ~5x vs serial.
MAX_PARALLEL_STATE_FETCHES = 4


class SidraLimitExceeded(Exception):
    """Raised when SIDRA refuses the request because it would return too many cells."""


class SidraRequestError(Exception):
    """Raised on any non-200, non-limit-exceeded SIDRA error."""


def _clean_column_name(name: str) -> str:
    """Normalize a SIDRA header to snake_case (ASCII)."""
    name = str(name).lower()
    replacements = {
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for src, dst in replacements.items():
        name = name.replace(src, dst)
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed_column"


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException, SidraRequestError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _http_get(url: str) -> requests.Response:
    # `Connection: close` disables HTTP keep-alive so each request opens (and
    # closes) its own TCP socket. This avoids urllib3 connection-pool deadlocks
    # observed when SIDRA closes idle sockets server-side faster than the
    # client notices, leaving threads waiting forever on dead pool entries.
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"Connection": "close", "User-Agent": "embrapa-commodities/0.1"},
    )
    if response.status_code == 200:
        return response
    if response.status_code in (400, 403):
        body = response.text.lower()
        if "limite" in body or "valores" in body:
            raise SidraLimitExceeded(body[:200])
    raise SidraRequestError(f"HTTP {response.status_code} for {url}: {response.text[:200]}")


def _periods_string(periods: list[int]) -> str:
    return f"{periods[0]}-{periods[-1]}" if len(periods) > 1 else str(periods[0])


def _fetch_block(
    table_id: str,
    periods: list[int],
    geo_level: str,
    geo_filter: str,
    classification: str,
    products: list[str],
) -> list[list[dict]]:
    """Fetch one SIDRA block. Returns a list of payloads (each with its own header row).

    On `SidraLimitExceeded`, the period is halved and the function recurses; if
    the period is already a single year, the exception propagates so the caller
    can decide whether to fall back to a different slicing strategy (e.g.
    per-state).
    """
    url = SIDRA_VALUES_URL.format(
        table_id=table_id,
        periods=_periods_string(periods),
        geo_level=geo_level,
        geo_filter=geo_filter,
        classification=classification,
        products=",".join(products),
    )
    logger.info(
        "SIDRA fetch t=%s p=%s geo=%s/%s products=%s",
        table_id, _periods_string(periods), geo_level, geo_filter, products,
    )
    try:
        response = _http_get(url)
    except SidraLimitExceeded:
        if len(periods) > 1:
            mid = len(periods) // 2
            args = (table_id, geo_level, geo_filter, classification, products)
            return (
                _fetch_block(args[0], periods[:mid], *args[1:])
                + _fetch_block(args[0], periods[mid:], *args[1:])
            )
        raise
    return [response.json()]


def _fetch_by_state_parallel(
    table_id: str,
    periods: list[int],
    classification: str,
    products: list[str],
) -> list[list[dict]]:
    """Fallback path: slice an n6 query by state with a thread pool."""
    payloads: list[list[dict]] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_STATE_FETCHES) as pool:
        future_to_state = {
            pool.submit(
                _fetch_block,
                table_id, periods, "n6", f"in n3 {state}", classification, products,
            ): state
            for state in BRAZIL_STATES
        }
        for future in as_completed(future_to_state):
            state = future_to_state[future]
            try:
                payloads.extend(future.result())
            except SidraLimitExceeded as exc:
                raise RuntimeError(
                    f"State {state} for period {_periods_string(periods)} alone exceeds the "
                    f"SIDRA cell limit. Reduce the period window or split by smaller units."
                ) from exc
            except Exception:
                logger.exception("State %s failed permanently", state)
                raise
    return payloads


def fetch_sidra_dataframe(
    table_id: str,
    start_year: int,
    end_year: int,
    classification: str,
    products: list[str],
    geo_level: str = "n6",
) -> pd.DataFrame:
    """Extract the full PEVS slice into a single DataFrame with snake_case headers.

    For municipal granularity (``geo_level='n6'``) we slice by state in parallel.
    Empirically this beats a single ``geo_filter='all'`` request for any
    realistic window: each state returns a small payload (~hundreds of KB),
    8 threads cover all 27 states in ~10 seconds, whereas a single ``all``
    response is ~17 MB and takes ~60s on its own.

    Per-state requests still go through ``_fetch_block``, so the recursive
    period-halving still kicks in if any individual state hits the SIDRA cell
    limit for a long-enough window.
    """
    periods = list(range(start_year, end_year + 1))

    if geo_level == "n6":
        payloads = _fetch_by_state_parallel(table_id, periods, classification, products)
    else:
        payloads = _fetch_block(table_id, periods, geo_level, "all", classification, products)

    frames: list[pd.DataFrame] = []
    for payload in payloads:
        if not payload or len(payload) < 2:
            continue
        # First row of every SIDRA payload is the human header — promote to columns.
        df = pd.DataFrame(payload)
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        frames.append(df)

    if not frames:
        raise RuntimeError("SIDRA returned no rows for the requested slice.")

    combined = pd.concat(frames, ignore_index=True)
    combined.columns = [_clean_column_name(c) for c in combined.columns]
    return combined


__all__ = [
    "BRAZIL_STATES",
    "SidraLimitExceeded",
    "SidraRequestError",
    "fetch_sidra_dataframe",
]
