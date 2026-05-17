"""HTTP client for the IBGE SIDRA values endpoint with adaptive slicing."""

from __future__ import annotations

import contextvars
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)

from embrapa_commodities import observability

logger = logging.getLogger(__name__)

# UF acronym for each IBGE n3 state code — used in events so the monitor shows
# "BA STUCK 2m" instead of "29 STUCK 2m".
STATE_CODE_TO_UF: dict[int, str] = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}  # fmt: skip

# Thread-local pointer to the state currently being fetched. Read by the
# tenacity before_sleep hook so retry events carry the state acronym.
_current_state: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_state", default=None
)

# All 27 Brazilian federative units (IBGE n3 codes).
BRAZIL_STATES: tuple[int, ...] = (
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    31,
    32,
    33,
    35,
    41,
    42,
    43,
    50,
    51,
    52,
    53,
)

SIDRA_VALUES_URL = "https://apisidra.ibge.gov.br/values/t/{table_id}/p/{periods}/v/all/{geo_level}/{geo_filter}/c{classification}/{products}"

# SIDRA returns at most this many cells per HTTP response. Going over triggers
# a 400 with "Limite de valores excedido".
SIDRA_CELL_LIMIT_PER_REQUEST = 100_000

# Minas Gerais has the most municipalities (853). Used as the worst-case denominator
# when sizing chunks — if MG fits under the cell limit, every other state does too.
LARGEST_STATE_MUNICIPALITY_COUNT = 853

# PEVS table 289 publishes 3 variables (`v/all` returns all): 144 (quantity),
# 145 (value), 1000145 (value as % of total).
SIDRA_T289_VARIABLES = 3


def recommended_chunk_years(n_products: int, safety: float = 0.7) -> int:
    """Compute the largest year-chunk that keeps every state response under
    SIDRA's per-request cell limit, with a 30% safety margin to absorb future
    municipality growth and per-request variability.

    cells_per_request = chunk_years * MG_municipalities * n_products * n_variables
    """
    if n_products <= 0:
        raise ValueError("n_products must be positive")
    safe_cells = int(SIDRA_CELL_LIMIT_PER_REQUEST * safety)
    denom = LARGEST_STATE_MUNICIPALITY_COUNT * SIDRA_T289_VARIABLES * n_products
    return max(1, safe_cells // denom)


# (connect_timeout, read_timeout). 30s read is the byte-idle deadline; if SIDRA
# stops sending bytes for that long, the request fails fast and tenacity retries.
# Combined with stop_after_delay below this caps total time spent on a single
# state, so a slow-byte hang can't strand the whole batch.
REQUEST_TIMEOUT: tuple[float, float] = (10.0, 30.0)

# Hard ceiling per state — after this many seconds across all retries, give up.
PER_STATE_DEADLINE_S: float = 180.0

# Empirical sweet spot: 4 workers with `Connection: close` avoids the urllib3
# pool deadlocks observed at 8 workers AND the connection-staleness hangs
# observed when reusing Keep-Alive sockets against SIDRA (which closes idle
# server-side connections aggressively).
MAX_PARALLEL_STATE_FETCHES = 4


RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


class SidraLimitExceeded(Exception):
    """Raised when SIDRA refuses the request because it would return too many cells."""


class SidraRequestError(Exception):
    """Raised on any non-200, non-limit-exceeded SIDRA error (base class)."""


class SidraTransientError(SidraRequestError):
    """Retryable SIDRA error (5xx, 408, 429, etc.)."""


def _clean_column_name(name: str) -> str:
    """Normalize a SIDRA header to snake_case (ASCII)."""
    name = str(name).lower()
    replacements = {
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for src, dst in replacements.items():
        name = name.replace(src, dst)
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "unnamed_column"


def _emit_retry(retry_state):  # type: ignore[no-untyped-def]
    """Tenacity before_sleep hook: emit structured event + warn the console."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    state = _current_state.get()
    observability.emit(
        "retry",
        state=state,
        attempt=retry_state.attempt_number,
        reason=str(exc)[:200] if exc else "?",
    )
    logger.warning(
        "Retrying SIDRA fetch state=%s attempt=%d: %s",
        state,
        retry_state.attempt_number,
        exc,
    )


@retry(
    reraise=True,
    # Stop on either attempt count OR cumulative time — the OR means a slow-
    # byte hang can't keep the worker alive past PER_STATE_DEADLINE_S even if
    # it never exhausts attempts.
    stop=stop_after_attempt(5) | stop_after_delay(PER_STATE_DEADLINE_S),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException, SidraTransientError)),
    before_sleep=_emit_retry,
)
def _http_get(url: str) -> requests.Response:
    # `Connection: close` forces a new TCP socket per request. Slower handshake
    # (~200ms) but avoids both urllib3 pool deadlocks AND server-side connection
    # staleness — both observed in benchmarks against SIDRA.
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
    msg = f"HTTP {response.status_code} for {url}: {response.text[:200]}"
    if response.status_code in RETRYABLE_STATUS_CODES:
        raise SidraTransientError(msg)
    raise SidraRequestError(msg)


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
        table_id,
        _periods_string(periods),
        geo_level,
        geo_filter,
        products,
    )
    try:
        response = _http_get(url)
    except SidraLimitExceeded:
        if len(periods) > 1:
            mid = len(periods) // 2
            args = (table_id, geo_level, geo_filter, classification, products)
            return _fetch_block(args[0], periods[:mid], *args[1:]) + _fetch_block(
                args[0], periods[mid:], *args[1:]
            )
        raise
    return [response.json()]


def _fetch_one_state(
    state_code: int,
    table_id: str,
    periods: list[int],
    classification: str,
    products: list[str],
) -> list[list[dict]]:
    """Per-state worker. Sets the contextvar so retry events carry the UF,
    and emits state_start / state_end / state_error around the fetch."""
    uf = STATE_CODE_TO_UF.get(state_code, str(state_code))
    token = _current_state.set(uf)
    started = time.monotonic()
    observability.emit("state_start", state=uf, state_code=state_code)
    try:
        payloads = _fetch_block(
            table_id, periods, "n6", f"in n3 {state_code}", classification, products
        )
        # Each payload's first row is the SIDRA header — exclude it from the count.
        rows = sum(max(0, len(p) - 1) for p in payloads)
        observability.emit(
            "state_end",
            state=uf,
            state_code=state_code,
            rows=rows,
            duration_s=round(time.monotonic() - started, 2),
        )
        return payloads
    except Exception as exc:
        observability.emit(
            "state_error",
            state=uf,
            state_code=state_code,
            error=str(exc)[:300],
            duration_s=round(time.monotonic() - started, 2),
        )
        raise
    finally:
        _current_state.reset(token)


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
                _fetch_one_state,
                state_code,
                table_id,
                periods,
                classification,
                products,
            ): state_code
            for state_code in BRAZIL_STATES
        }
        for future in as_completed(future_to_state):
            state_code = future_to_state[future]
            try:
                payloads.extend(future.result())
            except SidraLimitExceeded as exc:
                raise RuntimeError(
                    f"State {state_code} for period {_periods_string(periods)} alone exceeds "
                    f"the SIDRA cell limit. Reduce the period window or split by smaller units."
                ) from exc
            except Exception:
                logger.exception("State %s failed permanently", state_code)
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
