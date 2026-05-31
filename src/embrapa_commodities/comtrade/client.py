"""HTTP client for the UN Comtrade keyed JSON API.

One call returns annual bilateral trade for a *batch* of reporters across all
their partners (``partnerCode`` omitted) for the configured HS codes, flows and
years — the keyed endpoint accepts comma-lists for ``reporterCode`` / ``period``
/ ``cmdCode`` / ``flowCode`` but rejects the literal ``all`` for reporter, so the
pipeline enumerates reporters (from the public Reporters reference) and batches
them to stay under the per-call record cap.

The subscription key is sent **only** in the ``Ocp-Apim-Subscription-Key``
header — never in the URL or any log/error message — so it stays secret.
"""

from __future__ import annotations

import logging

import pandas as pd

from embrapa_commodities import observability
from embrapa_commodities.core import SourceTransientError
from embrapa_commodities.core import http as core_http

logger = logging.getLogger(__name__)

REPORTERS_REF_URL = "https://comtradeapi.un.org/files/v1/app/reference/Reporters.json"
HS_REF_URL = "https://comtradeapi.un.org/files/v1/app/reference/HS.json"

# Hard wall-clock ceilings (a keyed call returns up to ~100k JSON rows).
REQUEST_TOTAL_DEADLINE_S: float = 180.0
PER_CALL_DEADLINE_S: float = 300.0

# Keyed free-tier per-call record cap. A call that returns exactly this many rows
# has almost certainly been TRUNCATED server-side — even a single dense reporter
# (e.g. Germany, chapter 44 at HS6 × 4 regimes) hits it — so fetch_chunk_adaptive
# splits and recurses until every actual call stays under it.
PER_CALL_ROW_CAP: int = 100_000

# Curated Bronze columns kept from the ~50-field API response (dimensions +
# measures). Everything STRING in Bronze; the raw archive keeps the full frame.
BRONZE_COLUMNS: list[str] = [
    "refYear",
    "period",
    "reporterCode",
    "flowCode",
    "partnerCode",
    "partner2Code",
    "cmdCode",
    "customsCode",
    "mosCode",
    "motCode",
    "qtyUnitCode",
    "qty",
    "altQtyUnitCode",
    "altQty",
    "netWgt",
    "grossWgt",
    "cifvalue",
    "fobvalue",
    "primaryValue",
]


class ComtradeRequestError(Exception):
    """Non-200 response from the UN Comtrade API (base class)."""


class ComtradeTransientError(ComtradeRequestError, SourceTransientError):
    """Transient (retryable) error: 5xx/408/429 (incl. short rate limits)."""


def _emit_retry(retry_state):  # type: ignore[no-untyped-def]
    """Tenacity ``before_sleep`` hook: surface retries in ``embrapa monitor``."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    observability.emit(
        "retry",
        series="comtrade",
        window="",
        attempt=retry_state.attempt_number,
        reason=str(exc)[:200] if exc else "?",
    )
    logger.warning("Retrying Comtrade call attempt=%d: %s", retry_state.attempt_number, exc)


def list_reporters() -> list[str]:
    """All real reporter M49 codes (excluding group aggregates), from the public
    Reporters reference (no key needed). The keyed endpoint needs explicit codes
    since it rejects ``reporterCode=all``."""
    response = core_http.get_drained(
        REPORTERS_REF_URL,
        total_deadline_s=REQUEST_TOTAL_DEADLINE_S,
        transient_exc=ComtradeTransientError,
        context="Comtrade Reporters reference",
    )
    try:
        if response.status_code != 200:
            raise ComtradeTransientError(f"HTTP {response.status_code} for Reporters reference")
        results = response.json().get("results", [])
    finally:
        response.close()
    return [str(r["reporterCode"]) for r in results if not r.get("isGroup")]


def list_hs6_codes(scope_codes: list[str]) -> list[str]:
    """Every 6-digit HS leaf under the given scope codes (e.g. ``['0801', '44']``
    → all ``0801xx`` + ``44xxxx`` subheadings), from the public HS reference.

    Comtrade returns data only at the *requested* code level — asking for ``0801``
    yields the HS4 aggregate, not its children — so to ingest at HS6 the pipeline
    must enumerate the leaves. Returns them sorted; falls back to the scope codes
    themselves if a scope code has no 6-digit descendants (already a leaf)."""
    response = core_http.get_drained(
        HS_REF_URL,
        total_deadline_s=REQUEST_TOTAL_DEADLINE_S,
        transient_exc=ComtradeTransientError,
        context="Comtrade HS reference",
    )
    try:
        if response.status_code != 200:
            raise ComtradeTransientError(f"HTTP {response.status_code} for HS reference")
        results = response.json().get("results", [])
    finally:
        response.close()

    leaves: list[str] = []
    for entry in results:
        cid = str(entry["id"])
        if entry.get("aggrLevel") == 6 and any(cid.startswith(s) for s in scope_codes):
            leaves.append(cid)
    return sorted(leaves) if leaves else sorted(scope_codes)


@core_http.http_retry_policy(
    transient_exc=ComtradeTransientError,
    deadline_s=PER_CALL_DEADLINE_S,
    max_attempts=4,
    before_sleep=_emit_retry,
)
def fetch_chunk(
    base_url: str,
    api_key: str,
    *,
    reporters: list[str],
    years: list[int],
    cmd_codes: list[str],
    flows: list[str],
) -> pd.DataFrame:
    """One keyed call: annual bilateral trade for ``reporters`` × all partners,
    over ``years`` × ``cmd_codes`` × ``flows``. Returns a string-typed DataFrame
    of :data:`BRONZE_COLUMNS` (empty frame if the API returned no rows).

    ``partnerCode`` is omitted on purpose → every partner (the bilateral matrix,
    incl. ``0`` = World). The key goes in the header only.
    """
    params = {
        "reporterCode": ",".join(reporters),
        "period": ",".join(str(y) for y in years),
        "cmdCode": ",".join(cmd_codes),
        "flowCode": ",".join(flows),
    }
    url = f"{base_url.rstrip('/')}/C/A/HS?" + "&".join(f"{k}={v}" for k, v in params.items())
    headers = {**core_http.DEFAULT_HEADERS, "Ocp-Apim-Subscription-Key": api_key}
    # context omits the key and the (long) reporter list — just the shape.
    context = f"Comtrade {years} flows={flows} reporters={len(reporters)}"
    response = core_http.get_drained(
        url,
        total_deadline_s=REQUEST_TOTAL_DEADLINE_S,
        transient_exc=ComtradeTransientError,
        context=context,
        headers=headers,
    )
    try:
        if response.status_code != 200:
            msg = f"HTTP {response.status_code} for {context}"
            if response.status_code in core_http.RETRYABLE_STATUS_CODES:
                raise ComtradeTransientError(msg)
            raise ComtradeRequestError(msg)
        rows = response.json().get("data", [])
    finally:
        response.close()
    if not rows:
        return pd.DataFrame(columns=BRONZE_COLUMNS)
    frame = pd.DataFrame(rows)
    # Keep the curated columns, all as strings (Bronze convention); missing
    # columns (a sparse response) are added as NA via reindex.
    return frame.reindex(columns=BRONZE_COLUMNS).astype("string")


def fetch_chunk_adaptive(
    base_url: str,
    api_key: str,
    *,
    reporters: list[str],
    years: list[int],
    cmd_codes: list[str],
    flows: list[str],
) -> pd.DataFrame:
    """:func:`fetch_chunk` that guarantees completeness despite the per-call cap.

    A single keyed call silently truncates at :data:`PER_CALL_ROW_CAP` rows — and
    a lone dense reporter (Germany, chapter 44 at HS6 × 4 regimes) already hits it,
    so no fixed batch size is safe. When a call comes back at the cap, the largest
    divisible request dimension is split in half — reporters, then flows, then
    cmd codes — and the halves are fetched (recursively) and concatenated, so every
    real API call stays under the cap. A single (reporter, flow, cmd) that still
    caps is logged and returned as-is (only a partner split would help — not
    expected within the 0801+44 scope)."""
    df = fetch_chunk(
        base_url, api_key, reporters=reporters, years=years, cmd_codes=cmd_codes, flows=flows
    )
    if len(df) < PER_CALL_ROW_CAP:
        return df

    for name, seq in (("reporters", reporters), ("flows", flows), ("cmd_codes", cmd_codes)):
        if len(seq) > 1:
            mid = len(seq) // 2
            kwargs = {
                "reporters": reporters,
                "years": years,
                "cmd_codes": cmd_codes,
                "flows": flows,
            }
            kwargs[name] = seq[:mid]
            left = fetch_chunk_adaptive(base_url, api_key, **kwargs)
            kwargs[name] = seq[mid:]
            right = fetch_chunk_adaptive(base_url, api_key, **kwargs)
            return pd.concat([left, right], ignore_index=True)

    logger.warning(
        "Comtrade call still at the %d-row cap for a single reporter/flow/cmd "
        "(reporters=%s flows=%s cmd=%s) — data may be TRUNCATED.",
        PER_CALL_ROW_CAP,
        reporters,
        flows,
        cmd_codes,
    )
    return df
