"""Shared primitives every data-source module builds on.

What lives here: source-agnostic infrastructure that is naturally repeated
across ingestion pipelines (`SourceTransientError` marker, retry helpers,
delta helpers, observability wrappers) — see ``docs/adding_a_data_source.md``.

What does NOT live here: anything source-specific. The IBGE state-parallel
fetcher, the BCB series chunking, and other domain logic stay in their
respective ``ibge/`` / ``bcb/`` packages.
"""

from embrapa_dashboard.core.exceptions import SourceTransientError
from embrapa_dashboard.core.observability_helpers import (
    ChunkOutcome,
    ChunkTracker,
    IngestPartialFailure,
    chunked_run,
    pipeline_run,
    run_chunks,
)
from embrapa_dashboard.core.raw import (
    download_raw,
    land_raw,
    land_raw_file,
    list_raw,
    mark_raw_bronze_loaded,
    raw_bronze_loaded,
    raw_bronze_loaded_filter,
    raw_object_name,
    raw_provenance,
    read_raw,
)

__all__ = [
    "ChunkOutcome",
    "ChunkTracker",
    "IngestPartialFailure",
    "SourceTransientError",
    "chunked_run",
    "download_raw",
    "land_raw",
    "land_raw_file",
    "list_raw",
    "mark_raw_bronze_loaded",
    "pipeline_run",
    "raw_bronze_loaded",
    "raw_bronze_loaded_filter",
    "raw_object_name",
    "raw_provenance",
    "read_raw",
    "run_chunks",
]
