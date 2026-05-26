"""Real-time progress monitor for the Embrapa ingestion pipelines.

Public API:
    * :class:`MonitorState` — mutable aggregation of JSONL events seen so far.
    * :func:`run` — entry point used by ``embrapa monitor``: tails a JSONL log
      and renders a live Rich dashboard until pipeline_end / EOF / Ctrl-C.

Internal structure (split during the 2026-05 audit to keep each file under
the soft 500-LOC ceiling and to separate pure data from Rich-using UI):

* :mod:`embrapa_commodities.monitor.state` — event model, diagnosis
  heuristic (``_diagnose``), event summarisers (``_summarize``), and the
  ETA computations. No ``rich.*`` imports — testable in isolation.
* :mod:`embrapa_commodities.monitor.render` — Rich Panel/Table builders,
  per-status cell renderers, ``_tail_jsonl``, and the main ``run`` loop.

Private symbols below are re-exported so the existing
``tests/test_monitor.py`` import paths keep working without touching every
``from embrapa_commodities.monitor import _foo`` line.
"""

from __future__ import annotations

from embrapa_commodities.monitor.render import (
    _build_state_grid,
    _render,
    _render_state_cell,
    _tail_jsonl,
    run,
)
from embrapa_commodities.monitor.state import (
    ERROR_HISTORY,
    PARALLEL_STATE_FETCHES,
    RECENT_EVENTS,
    STATE_DUR_WINDOW,
    STATES_PER_CHUNK,
    STUCK_THRESHOLD_S,
    MonitorState,
    _chunk_eta,
    _diagnose,
    _fmt_duration,
    _fmt_eta,
    _pipeline_eta,
    _state_eta,
    _summarize,
)

__all__ = [
    "ERROR_HISTORY",
    "PARALLEL_STATE_FETCHES",
    "RECENT_EVENTS",
    "STATES_PER_CHUNK",
    "STATE_DUR_WINDOW",
    "STUCK_THRESHOLD_S",
    "MonitorState",
    "_build_state_grid",
    "_chunk_eta",
    "_diagnose",
    "_fmt_duration",
    "_fmt_eta",
    "_pipeline_eta",
    "_render",
    "_render_state_cell",
    "_state_eta",
    "_summarize",
    "_tail_jsonl",
    "run",
]
