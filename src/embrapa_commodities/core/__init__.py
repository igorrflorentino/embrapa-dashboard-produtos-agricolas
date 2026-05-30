"""Shared primitives every data-source module builds on.

What lives here: source-agnostic infrastructure that is naturally repeated
across ingestion pipelines (`SourceTransientError` marker, retry helpers,
delta helpers, observability wrappers) — see ``docs/adding_a_data_source.md``.

What does NOT live here: anything source-specific. The IBGE state-parallel
fetcher, the BCB series chunking, and other domain logic stay in their
respective ``ibge/`` / ``bcb/`` packages.
"""

from embrapa_commodities.core.bronze import land_and_load
from embrapa_commodities.core.exceptions import SourceTransientError
from embrapa_commodities.core.observability_helpers import pipeline_run

__all__ = ["SourceTransientError", "land_and_load", "pipeline_run"]
