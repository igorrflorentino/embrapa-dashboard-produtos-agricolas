"""Cross-source exception markers."""

from __future__ import annotations


class SourceTransientError(Exception):
    """Marker for retryable upstream-API failures across every data source.

    Each source's client module defines its own concrete transient class
    (``SidraTransientError``, ``BcbTransientError``, ...) so handlers can
    still distinguish origins; those concrete classes inherit from this one
    via mixin so anything written against ``SourceTransientError`` catches
    them uniformly without listing each by name. The shared tenacity
    decorator in :mod:`embrapa_commodities.core.http` (``http_retry_policy``)
    is the primary consumer of this contract.

    New sources: define your own ``<Source>TransientError`` that includes
    ``SourceTransientError`` in its bases. See
    ``docs/adding_a_data_source.md``.
    """
