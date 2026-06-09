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
    """Transient (retryable) error: 5xx/408 (incl. short reference-file hiccups)."""


class ComtradeQuotaError(ComtradeRequestError):
    """The daily keyed-call quota is exhausted (HTTP 429 on a keyed data call).

    Deliberately **not** a :class:`SourceTransientError`: the shared retry policy
    must not retry it. Retrying would only burn the (already spent) daily budget;
    the resumable two-phase raw zone means the right move is to stop and re-run
    later, which picks up exactly the un-archived chunks. The pipeline catches
    this to break its chunk loop early ("quota exhausted — re-run to resume").

    Scoped to keyed *data* calls (:func:`fetch_chunk`); a 429 on the public,
    key-less reference files (:func:`list_reporters` / :func:`list_hs6_codes`) is
    a momentary rate limit and stays transient/retryable.
    """


class ComtradeTruncationError(ComtradeRequestError):
    """A single (reporter, flow, cmd) call still hit the per-call row cap.

    The adaptive splitter has nothing left to split (reporters/flows/cmd are all
    singletons) yet the call came back at :data:`PER_CALL_ROW_CAP` — only a
    partner-dimension split would help, which the keyed endpoint can't express.
    Rather than silently archive a TRUNCATED chunk (which the resume logic would
    then treat as complete forever), the fetch raises this so the chunk is left
    un-archived and a later run re-attempts it. Non-transient: an immediate retry
    of the identical call would truncate identically.
    """


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
    must enumerate the leaves. Returns them sorted.

    Raises rather than falling back to the (HS4) scope codes: an empty reference is
    treated as a transient fetch failure, and a non-empty reference with no HS6
    descendants of the scope is a configuration error. Silently returning the
    scope codes would request HS4 aggregates — the exact wrong-granularity /
    double-count failure HS6 exists to avoid."""
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

    if not results:
        # 200 with an empty body — an API hiccup or schema drift; retryable.
        raise ComtradeTransientError("HS reference returned no results")
    leaves = sorted(
        str(entry["id"])
        for entry in results
        if entry.get("aggrLevel") == 6 and any(str(entry["id"]).startswith(s) for s in scope_codes)
    )
    if not leaves:
        raise ComtradeRequestError(
            f"No HS6 leaves under scope {scope_codes} in the HS reference "
            "— check COMTRADE_CMD_CODES."
        )
    return leaves


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
            if response.status_code == 429:
                # Daily keyed-call quota — stop, don't retry (see ComtradeQuotaError).
                raise ComtradeQuotaError(f"quota exhausted ({msg}) — re-run to resume")
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
    real API call stays under the cap.

    A single (reporter, flow, cmd) that *still* caps cannot be split further (only
    a partner split would help, which the keyed endpoint can't express). Rather
    than return the truncated frame and let it be archived as if complete, this
    emits a ``truncated`` event and raises :class:`ComtradeTruncationError` so the
    chunk is left un-archived for a later run to re-attempt (not expected within
    the 0801+44 scope)."""
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

    observability.emit(
        "truncated",
        series="comtrade",
        reporters=",".join(reporters),
        flows=",".join(flows),
        cmd_codes=",".join(cmd_codes),
        years=",".join(str(y) for y in years),
        row_cap=PER_CALL_ROW_CAP,
    )
    logger.error(
        "Comtrade call still at the %d-row cap for a single reporter/flow/cmd "
        "(reporters=%s flows=%s cmd=%s) — refusing to archive a TRUNCATED chunk; "
        "it will be retried on the next run.",
        PER_CALL_ROW_CAP,
        reporters,
        flows,
        cmd_codes,
    )
    raise ComtradeTruncationError(
        f"truncated at {PER_CALL_ROW_CAP} rows for reporters={reporters} "
        f"flows={flows} cmd={cmd_codes}"
    )
