"""HTTP client for the MDIC Comex Stat bulk CSV files.

This is a *file downloader*, not a JSON API client: each call fetches one
per-year, per-flow CSV (``EXP_<ano>.csv`` / ``IMP_<ano>.csv``, ``;``-separated,
latin-1, history since 1997) and filters it down to the configured products
locally. Two deliberate departures from the BCB/IBGE clients, both forced by
the file sizes (tens to hundreds of MB):

1. **Stream to disk, not memory.** ``core_http.get_drained`` buffers the whole
   body in RAM — fine for small JSON payloads, wrong for a 100 MB CSV. So the
   download here streams ``iter_content`` straight to a temp file under its own
   wall-clock deadline, reusing only the shared retry *policy*.
2. **Chunked parse + early column filter.** ``pandas.read_csv(chunksize=...)``
   keeps memory bounded while we keep only rows whose ``CO_NCM`` matches a
   configured 8-digit code or whose first two digits match a configured HS
   chapter. The filter is column-precise on ``CO_NCM`` on purpose: a substring
   match on the raw line would false-match e.g. country code ``445`` for
   chapter ``44``.

Shape confirmed live (2026-05-30) against EXP/IMP_{1997,2023,2026}: EXP has 11
columns; IMP adds ``VL_FRETE`` and ``VL_SEGURO``. The two schemas are unioned
(:data:`SOURCE_COLUMNS`) so export rows simply carry NULL for the two
import-only columns.
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
import time
from pathlib import Path

import certifi
import pandas as pd
import requests

from embrapa_commodities import observability
from embrapa_commodities.comex._ca import SECTIGO_INTERMEDIATE_PEM
from embrapa_commodities.core import SourceTransientError
from embrapa_commodities.core import http as core_http

logger = logging.getLogger(__name__)

# Base path holding the per-year NCM files. The full URL is
# ``{base}/{EXP|IMP}_{year}.csv``.
DEFAULT_BASE_URL = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm"

# Export columns (11). Import is a strict superset adding the two below.
EXP_COLUMNS: list[str] = [
    "CO_ANO",
    "CO_MES",
    "CO_NCM",
    "CO_UNID",
    "CO_PAIS",
    "SG_UF_NCM",
    "CO_VIA",
    "CO_URF",
    "QT_ESTAT",
    "KG_LIQUIDO",
    "VL_FOB",
]
IMP_ONLY_COLUMNS: list[str] = ["VL_FRETE", "VL_SEGURO"]
# Union schema every Bronze row is reindexed onto: export rows get NULL for the
# two import-only columns.
SOURCE_COLUMNS: list[str] = [*EXP_COLUMNS, *IMP_ONLY_COLUMNS]

# Logical flow → file-name prefix. Also the closed domain accepted in .env.
FILE_PREFIX: dict[str, str] = {"export": "EXP", "import": "IMP"}

# Per-attempt wall-clock ceiling for one file download. A ~100 MB file over a
# slow link can legitimately take minutes; this only guards against a
# slow-byte hang (1 byte every <read-timeout seconds) stranding the worker.
DOWNLOAD_DEADLINE_S: float = 1200.0
# Cumulative ceiling across all retries for one file — keeps a single stuck
# file from blocking the whole multi-year ingest indefinitely.
RETRY_TOTAL_DEADLINE_S: float = 3600.0
# Rows per pandas read chunk while filtering — bounds memory on huge files.
PARSE_CHUNK_ROWS: int = 200_000


_ca_bundle_path: str | None = None


def _ca_bundle() -> str:
    """Path to a CA bundle = certifi + the vendored Sectigo intermediate.

    The Comex host omits its issuing intermediate from the TLS handshake, so
    plain certifi verification fails (see :mod:`embrapa_commodities.comex._ca`).
    Appending the intermediate to certifi's roots lets ``requests`` verify
    without ever disabling TLS checks. Built once and cached for the process.
    """
    global _ca_bundle_path
    if _ca_bundle_path and os.path.exists(_ca_bundle_path):
        return _ca_bundle_path
    base = Path(certifi.where()).read_text(encoding="ascii")
    fd, path = tempfile.mkstemp(prefix="comex_ca_", suffix=".pem")
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(base)
        fh.write("\n")
        fh.write(SECTIGO_INTERMEDIATE_PEM)
    _ca_bundle_path = path
    return path


class ComexRequestError(Exception):
    """Non-200 response from the Comex Stat file host (base class)."""


class ComexTransientError(ComexRequestError, SourceTransientError):
    """Transient (retryable) error: 5xx/408/429 or a slow-byte download hang."""


def _emit_retry(retry_state):  # type: ignore[no-untyped-def]
    """Tenacity ``before_sleep`` hook: surface download retries in ``embrapa monitor``.

    Mirrors the BCB client — the retried function is :func:`_download_to_disk`,
    so the (url, dest) context comes straight off ``retry_state.args``.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    args = retry_state.args
    url = args[0] if args else retry_state.kwargs.get("url", "?")
    observability.emit(
        "retry",
        series=str(url).rsplit("/", 1)[-1],  # the EXP_2023.csv basename
        window="",
        attempt=retry_state.attempt_number,
        reason=str(exc)[:200] if exc else "?",
    )
    logger.warning(
        "Retrying Comex download url=%s attempt=%d: %s",
        url,
        retry_state.attempt_number,
        exc,
    )


@core_http.http_retry_policy(
    transient_exc=ComexTransientError,
    deadline_s=RETRY_TOTAL_DEADLINE_S,
    max_attempts=3,
    before_sleep=_emit_retry,
)
def _download_to_disk(url: str, dest_path: str) -> None:
    """Stream one CSV to ``dest_path`` under a wall-clock deadline.

    Raises :class:`ComexTransientError` on retryable HTTP status or a slow-byte
    hang, :class:`ComexRequestError` on a permanent 4xx (e.g. 404 for a year
    that doesn't exist yet).
    """
    deadline = time.monotonic() + DOWNLOAD_DEADLINE_S
    logger.info("Comex download %s", url)
    with requests.get(
        url,
        stream=True,
        timeout=core_http.DEFAULT_TIMEOUT,
        headers=core_http.DEFAULT_HEADERS,
        verify=_ca_bundle(),
    ) as response:
        if response.status_code != 200:
            msg = f"HTTP {response.status_code} for {url}"
            if response.status_code in core_http.RETRYABLE_STATUS_CODES:
                raise ComexTransientError(msg)
            raise ComexRequestError(msg)
        with open(dest_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if time.monotonic() > deadline:
                    raise ComexTransientError(
                        f"download exceeded {DOWNLOAD_DEADLINE_S}s total budget "
                        f"(slow-byte hang) for {url}"
                    )
                if chunk:
                    fh.write(chunk)


def _read_filtered(path: str, ncm_codes: set[str], chapter_codes: set[str]) -> pd.DataFrame:
    """Parse a Comex CSV in chunks, keeping only the configured products.

    A row is kept when its ``CO_NCM`` is in ``ncm_codes`` *or* its first two
    digits are in ``chapter_codes``. Returns a string-typed frame with exactly
    :data:`SOURCE_COLUMNS` (import-only columns are NULL for export files).
    """
    frames: list[pd.DataFrame] = []
    reader = pd.read_csv(
        path,
        sep=";",
        encoding="latin-1",
        dtype=str,
        chunksize=PARSE_CHUNK_ROWS,
    )
    for chunk in reader:
        ncm = chunk["CO_NCM"].astype(str)
        mask = ncm.isin(ncm_codes) | ncm.str[:2].isin(chapter_codes)
        selected = chunk[mask]
        if not selected.empty:
            frames.append(selected)
    if not frames:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    # Reindex onto the union schema so export files gain NULL VL_FRETE/VL_SEGURO
    # and column order is canonical regardless of the source flow.
    return combined.reindex(columns=SOURCE_COLUMNS)


def fetch_flow_year(
    base_url: str,
    flow: str,
    year: int,
    *,
    ncm_codes: set[str],
    chapter_codes: set[str],
) -> pd.DataFrame:
    """Download one (flow, year) Comex file and return the filtered rows.

    ``flow`` must be a key of :data:`FILE_PREFIX` (``export``/``import``). The
    returned frame has :data:`SOURCE_COLUMNS`; it carries no ``flow`` or
    ``ingestion_timestamp`` column — those are stamped by the pipeline.
    """
    prefix = FILE_PREFIX[flow]
    url = f"{base_url.rstrip('/')}/{prefix}_{year}.csv"
    fd, path = tempfile.mkstemp(prefix=f"comex_{prefix}_{year}_", suffix=".csv")
    os.close(fd)
    try:
        _download_to_disk(url, path)
        return _read_filtered(path, ncm_codes, chapter_codes)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)
