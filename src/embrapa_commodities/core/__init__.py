"""Shared primitives every data-source module builds on.

What lives here: source-agnostic infrastructure that is naturally repeated
across ingestion pipelines (`SourceTransientError` marker, retry helpers,
delta helpers, observability wrappers) — see ``docs/adding_a_data_source.md``.

What does NOT live here: anything source-specific. The IBGE state-parallel
fetcher, the BCB series chunking, and other domain logic stay in their
respective ``ibge/`` / ``bcb/`` packages.
"""

from embrapa_commodities.core.exceptions import SourceTransientError

__all__ = ["SourceTransientError"]
