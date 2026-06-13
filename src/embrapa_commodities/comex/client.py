"""HTTP client for the MDIC Comex Stat bulk CSV files.

This is a *file downloader*, not a JSON API client: each call fetches one
per-year, per-flow CSV (``EXP_<year>.csv`` / ``IMP_<year>.csv``, ``;``-separated,
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
from io import BytesIO
from pathlib import Path

import certifi
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
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


def _head_retry_url(args: tuple, kwargs: dict) -> str:
    """Rebuild the probed file URL for a ``head_source(base_url, flow, year)`` retry.

    ``args[0]`` is only the *base* URL, so the file URL must be rebuilt from
    ``(flow, year)`` or every freshness probe would be misattributed to the base
    path's last segment (one bogus ``ncm`` series)."""
    base_url = args[0] if len(args) > 0 else kwargs.get("base_url", "?")
    flow = args[1] if len(args) > 1 else kwargs.get("flow", "?")
    year = args[2] if len(args) > 2 else kwargs.get("year", "?")
    try:
        return file_url(str(base_url), str(flow), year)
    except KeyError:  # unknown flow — fall back to the base URL
        return str(base_url)


def _emit_retry(retry_state):  # type: ignore[no-untyped-def]
    """Tenacity ``before_sleep`` hook: surface retries in ``embrapa monitor``.

    Wired to two retried functions with different signatures:
    :func:`_download_to_disk(url, dest)` and :func:`head_source(base_url, flow,
    year)`.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    args = retry_state.args or ()
    kwargs = retry_state.kwargs or {}
    is_head = getattr(getattr(retry_state, "fn", None), "__name__", "") == "head_source"
    if is_head:
        op = "HEAD"
        url = _head_retry_url(args, kwargs)
    else:
        op = "download"
        url = args[0] if args else kwargs.get("url", "?")
    observability.emit(
        "retry",
        series=str(url).rsplit("/", 1)[-1],  # the EXP_2023.csv basename
        window="",
        attempt=retry_state.attempt_number,
        reason=str(exc)[:200] if exc else "?",
    )
    logger.warning(
        "Retrying Comex %s url=%s attempt=%d: %s",
        op,
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


def file_url(base_url: str, flow: str, year: int) -> str:
    """The Comex Stat CSV URL for one ``(flow, year)`` — ``{base}/{EXP|IMP}_{year}.csv``."""
    return f"{base_url.rstrip('/')}/{FILE_PREFIX[flow]}_{year}.csv"


@core_http.http_retry_policy(
    transient_exc=ComexTransientError,
    deadline_s=120.0,
    max_attempts=3,
    before_sleep=_emit_retry,
)
def head_source(base_url: str, flow: str, year: int) -> dict[str, str]:
    """HEAD a ``(flow, year)`` file and return its provenance headers.

    Returns ``{source_url, source_etag?, source_last_modified?,
    source_content_length?}`` — the freshness fingerprint a two-phase sync
    compares against the archived raw object's stored provenance to decide
    whether to re-download. Raises like :func:`_download_to_disk` on HTTP error.
    """
    url = file_url(base_url, flow, year)
    response = requests.head(
        url,
        timeout=core_http.DEFAULT_TIMEOUT,
        headers=core_http.DEFAULT_HEADERS,
        allow_redirects=True,
        verify=_ca_bundle(),
    )
    if response.status_code != 200:
        msg = f"HTTP {response.status_code} (HEAD) for {url}"
        if response.status_code in core_http.RETRYABLE_STATUS_CODES:
            raise ComexTransientError(msg)
        raise ComexRequestError(msg)
    provenance = {"source_url": url}
    for header, key in (
        ("ETag", "source_etag"),
        ("Last-Modified", "source_last_modified"),
        ("Content-Length", "source_content_length"),
    ):
        value = response.headers.get(header)
        if value:
            provenance[key] = value
    return provenance


def _csv_to_parquet(csv_path: str, parquet_path: str) -> int:
    """Convert a Comex CSV to Parquet in chunks (memory-bounded). Returns row count.

    Verbatim: every column STRING, every row, no filtering — this is the raw
    archive. Streaming via ``ParquetWriter`` keeps peak memory at one chunk even
    for the ~1.5M-row full-year files.
    """
    writer: pq.ParquetWriter | None = None
    rows = 0
    try:
        reader = pd.read_csv(
            csv_path, sep=";", encoding="latin-1", dtype=str, chunksize=PARSE_CHUNK_ROWS
        )
        for chunk in reader:
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(parquet_path, table.schema, compression="snappy")
            writer.write_table(table)
            rows += len(chunk)
    finally:
        if writer is not None:
            writer.close()
    return rows


def extract_to_parquet(base_url: str, flow: str, year: int, parquet_path: str) -> int:
    """Phase 1: download one ``(flow, year)`` CSV and write it verbatim to Parquet.

    Returns the row count. The CSV is streamed to a temp file, then converted to
    Parquet in chunks, so neither step holds the whole file in memory.
    """
    fd, csv_path = tempfile.mkstemp(prefix=f"comex_{FILE_PREFIX[flow]}_{year}_", suffix=".csv")
    os.close(fd)
    try:
        _download_to_disk(file_url(base_url, flow, year), csv_path)
        return _csv_to_parquet(csv_path, parquet_path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(csv_path)


def filter_products(
    raw_parquet: bytes, ncm_codes: set[str], chapter_codes: set[str]
) -> pd.DataFrame:
    """Phase 2: filter a raw Parquet (all NCMs) to the configured products.

    A row is kept when ``CO_NCM`` is in ``ncm_codes`` or its first two digits are
    in ``chapter_codes`` (column-precise — a substring match on the raw line
    would false-hit country code 445 for chapter 44). Streams via
    ``iter_batches`` so memory stays bounded. Returns a frame with exactly
    :data:`SOURCE_COLUMNS` (import-only columns NULL for export files).
    """
    parquet_file = pq.ParquetFile(BytesIO(raw_parquet))
    frames: list[pd.DataFrame] = []
    for batch in parquet_file.iter_batches(batch_size=PARSE_CHUNK_ROWS):
        chunk = batch.to_pandas()
        ncm = chunk["CO_NCM"].astype(str)
        mask = ncm.isin(ncm_codes) | ncm.str[:2].isin(chapter_codes)
        selected = chunk[mask]
        if not selected.empty:
            frames.append(selected)
    if not frames:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    return pd.concat(frames, ignore_index=True).reindex(columns=SOURCE_COLUMNS)
