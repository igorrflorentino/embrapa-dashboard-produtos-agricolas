"""Real-time progress monitor.

Tails a JSONL event log produced by :mod:`embrapa_commodities.observability`
and renders a live Rich dashboard:
    * elapsed + ETA at three scopes (pipeline / chunk / current-state grid),
    * progress bars for chunks and states-within-current-chunk,
    * per-UF status grid with stuck detection,
    * recent-events tail,
    * error panel with heuristic diagnosis below the tail.

The render loop ticks once per second regardless of new events so timers and
ETAs keep moving even when SIDRA stalls. Each tick drains all log lines that
appeared since the previous tick before re-rendering.

Invoked from the CLI as ``embrapa monitor`` (latest run) or
``embrapa monitor <path-to-jsonl>``.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# A state with no event for this long is flagged "STUCK". Calibrated to
# SIDRA's typical per-state response (<5s) plus a few retry-and-backoff cycles.
STUCK_THRESHOLD_S = 90
# How many recent events to keep on screen.
RECENT_EVENTS = 8
# How many error history entries to keep + display.
ERROR_HISTORY = 6
# Brazilian federative units that IBGE PEVS covers — used as the state-bar total.
STATES_PER_CHUNK = 27
# IBGE client paralellism — matches MAX_PARALLEL_STATE_FETCHES in ibge.client.
PARALLEL_STATE_FETCHES = 4
# Sliding window of state durations used for ETAs — keep one chunk's worth.
STATE_DUR_WINDOW = 27


def _parse_ts(s: str) -> float:
    """ISO-8601 → epoch seconds (UTC). Falls back to time.time() on parse error."""
    try:
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return time.time()


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def _fmt_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "?"
    return _fmt_duration(seconds)


# Each entry is (patterns, message).  ``patterns`` is a tuple of lowercase
# substrings; **any** match triggers the diagnosis.  Order matters — first
# match wins, just like the old ``if/elif`` chain, but the loop reduces
# cyclomatic complexity from D(30) to A(3).
_DIAGNOSIS_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (
        ("read timed out", "read timeout"),
        "SIDRA parou de enviar bytes (slow-byte) — pode ser sobrecarga ou conexão instável.",
    ),
    (
        ("connection refused",),
        "Conexão recusada — IBGE pode estar em manutenção ou bloqueando seu IP.",
    ),
    (
        ("connection reset", "remotedisconnected"),
        "Conexão resetada pelo servidor durante a resposta — SIDRA instável agora.",
    ),
    (
        ("name or service not known", "nodename nor servname"),
        "Falha de DNS — verifique sua conexão com a internet.",
    ),
    (
        ("limite de valores", "limite excedido"),
        "Limite de células do SIDRA estourado — reduza --chunk-years ou número de produtos.",
    ),
    (
        ("retryerror", "stop_after_delay", "stop_after_attempt"),
        "Deadline de 180s por estado esgotado após múltiplos retries — SIDRA muito lento.",
    ),
    (
        ("401", "unauthorized"),
        "Não autenticado — rode `gcloud auth application-default login`.",
    ),
    (
        ("403", "forbidden"),
        "Sem permissão — verifique IAM no GCP_PROJECT_ID.",
    ),
    (
        ("404", "not found"),
        "Recurso não encontrado — confira IBGE_TABLE_ID e códigos de produto.",
    ),
    (
        ("500", "502", "503", "504"),
        "Servidor SIDRA retornou erro 5xx — fora do ar temporariamente, retente em alguns minutos.",
    ),
    (
        ("ssl", "certificate"),
        "Erro de SSL — verifique data/hora do sistema e certificados raiz.",
    ),
    (
        ("memoryerror", "out of memory"),
        "Memória insuficiente — reduza --chunk-years.",
    ),
    # Two-condition pattern: both "permission denied" AND "gs://" must appear.
    # Handled specially in the loop below.
    (
        ("returned no rows", "no rows for the requested"),
        "SIDRA retornou vazio — provavelmente o ano ainda não foi publicado "
        "(PEVS tem ~1 ano de defasagem). Ajuste IBGE_END_YEAR.",
    ),
]

_GCS_PERMISSION_DIAGNOSIS = "Sem permissão no bucket GCS — verifique IAM."
_FALLBACK_DIAGNOSIS = "Sem diagnóstico automático — veja a mensagem completa."


def _diagnose(error_text: str) -> str:
    """Map a raw error message to a probable-cause line in Portuguese.

    Heuristic-only; runs on every error event so keep the cost low (lowercased
    substring matches against :data:`_DIAGNOSIS_PATTERNS`).  Returns a short
    sentence ending in a period.
    """
    if not error_text:
        return "Sem mensagem de erro registrada."
    e = error_text.lower()

    # Two-condition special case (both substrings must match).
    if "permission denied" in e and "gs://" in e:
        return _GCS_PERMISSION_DIAGNOSIS

    for patterns, message in _DIAGNOSIS_PATTERNS:
        if any(p in e for p in patterns):
            return message

    return _FALLBACK_DIAGNOSIS


class MonitorState:
    """Mutable in-memory aggregation of events seen so far."""

    def __init__(self) -> None:
        self.pipeline: str | None = None
        self.run_id: str | None = None
        self.params: dict[str, Any] = {}
        self.started_at: float | None = None
        self.ended_at: float | None = None
        self.chunks_total: int = 0
        self.chunks_done: int = 0
        self.chunks_failed: int = 0
        self.active_chunk: str | None = None
        self.active_chunk_started_at: float | None = None
        self.rows_total: int = 0
        self.retries: int = 0
        self.errors: int = 0
        # state_acronym → {"status", "rows", "duration_s", "started_at", "last_seen"}
        self.states: dict[str, dict[str, Any]] = {}
        self.recent: deque[tuple[str, str, str]] = deque(maxlen=RECENT_EVENTS)
        self.last_event_at: float | None = None
        # ── ETA fuel ──────────────────────────────────────────────────────
        self.chunk_durations: list[float] = []
        # Sliding window so a slow state long ago doesn't bias the chunk ETA forever.
        self.state_durations: deque[float] = deque(maxlen=STATE_DUR_WINDOW)
        # ── Errors panel ──────────────────────────────────────────────────
        self.error_history: deque[dict[str, Any]] = deque(maxlen=ERROR_HISTORY)

    def apply(self, ev: dict[str, Any]) -> None:
        """Dispatch a single event dict to the appropriate handler."""
        ts = _parse_ts(ev.get("ts", ""))
        evt = ev.get("event", "?")
        self.last_event_at = ts
        summary = _summarize(ev)
        self.recent.append((datetime.fromtimestamp(ts, UTC).strftime("%H:%M:%S"), evt, summary))

        handler = self._handlers.get(evt)
        if handler is not None:
            handler(self, ev, ts)

    # ── Per-event handlers (private, called via dispatch table) ────────

    def _on_pipeline_start(self, ev: dict[str, Any], ts: float) -> None:
        self.pipeline = ev.get("pipeline")
        self.run_id = ev.get("run_id")
        self.params = ev.get("params", {})
        self.started_at = ts
        self.chunks_total = int(ev.get("chunks_total", 0) or 0)

    def _on_chunk_start(self, ev: dict[str, Any], ts: float) -> None:
        self.active_chunk = ev.get("chunk_id")
        self.active_chunk_started_at = ts
        # New chunk → fresh state grid (each chunk is a new sweep of UFs).
        self.states = {}

    def _on_state_start(self, ev: dict[str, Any], ts: float) -> None:
        uf = ev.get("state", "?")
        self.states[uf] = {
            "status": "running",
            "rows": None,
            "duration_s": None,
            "started_at": ts,
            "last_seen": ts,
        }

    def _on_state_end(self, ev: dict[str, Any], ts: float) -> None:
        uf = ev.get("state", "?")
        self.states.setdefault(uf, {"started_at": ts})
        self.states[uf].update(
            status="ok",
            rows=ev.get("rows"),
            duration_s=ev.get("duration_s"),
            last_seen=ts,
        )
        d = ev.get("duration_s")
        if isinstance(d, int | float):
            self.state_durations.append(float(d))

    def _on_state_error(self, ev: dict[str, Any], ts: float) -> None:
        uf = ev.get("state", "?")
        self.states.setdefault(uf, {"started_at": ts})
        err = ev.get("error", "?")
        self.states[uf].update(status="error", error=err, last_seen=ts)
        self.errors += 1
        self.error_history.append({"ts": ts, "kind": "state", "target": uf, "error": str(err)})

    def _on_retry(self, ev: dict[str, Any], ts: float) -> None:
        self.retries += 1
        # Refresh the last_seen of the state so it doesn't go STUCK while retrying.
        uf = ev.get("state")
        if uf and uf in self.states:
            self.states[uf]["last_seen"] = ts

    def _on_ingest_loaded(self, ev: dict[str, Any], ts: float) -> None:
        self.rows_total += int(ev.get("rows", 0) or 0)

    def _on_chunk_end(self, ev: dict[str, Any], ts: float) -> None:
        self.chunks_done += 1
        self.rows_total += int(ev.get("rows", 0) or 0)
        d = ev.get("duration_s")
        if isinstance(d, int | float):
            self.chunk_durations.append(float(d))
        self.active_chunk = None
        self.active_chunk_started_at = None

    def _on_chunk_error(self, ev: dict[str, Any], ts: float) -> None:
        self.chunks_failed += 1
        err = ev.get("error", "?")
        chunk_id = ev.get("chunk_id", "?")
        self.errors += 1
        self.error_history.append(
            {"ts": ts, "kind": "chunk", "target": chunk_id, "error": str(err)}
        )
        d = ev.get("duration_s")
        if isinstance(d, int | float):
            # Count failed chunk durations too — they reflect real wall-clock cost.
            self.chunk_durations.append(float(d))
        self.active_chunk = None
        self.active_chunk_started_at = None

    def _on_pipeline_end(self, ev: dict[str, Any], ts: float) -> None:
        self.ended_at = ts

    # Dispatch table — class-level, built once.
    _handlers: ClassVar[dict[str, Any]] = {
        "pipeline_start": _on_pipeline_start,
        "chunk_start": _on_chunk_start,
        "state_start": _on_state_start,
        "state_end": _on_state_end,
        "state_error": _on_state_error,
        "retry": _on_retry,
        "ingest_loaded": _on_ingest_loaded,
        "chunk_end": _on_chunk_end,
        "chunk_error": _on_chunk_error,
        "pipeline_end": _on_pipeline_end,
    }


# ── Event summarisers ────────────────────────────────────────────────────


def _summarize_pipeline_start(ev: dict[str, Any]) -> str:
    p = ev.get("pipeline")
    params = ev.get("params", {})
    return (
        f"{p} years={params.get('start_year')}-{params.get('end_year')} "
        f"chunks={ev.get('chunks_total', '?')}"
    )


def _summarize_chunk_start(ev: dict[str, Any]) -> str:
    return f"chunk {ev.get('chunk_n', '?')}/{ev.get('chunk_total', '?')} → {ev.get('chunk_id')}"


def _summarize_chunk_end(ev: dict[str, Any]) -> str:
    return (
        f"chunk {ev.get('chunk_id')} ok rows={ev.get('rows', 0):,} {ev.get('duration_s', 0):.1f}s"
    )


def _summarize_chunk_error(ev: dict[str, Any]) -> str:
    return f"chunk {ev.get('chunk_id')} FAILED {str(ev.get('error', '?'))[:60]}"


def _summarize_state_end(ev: dict[str, Any]) -> str:
    return f"{ev.get('state')} ok rows={ev.get('rows', 0):,} {ev.get('duration_s', 0):.1f}s"


def _summarize_state_error(ev: dict[str, Any]) -> str:
    return f"{ev.get('state')} ERROR {str(ev.get('error', ''))[:60]}"


def _summarize_retry(ev: dict[str, Any]) -> str:
    return (
        f"retry {ev.get('state', '?')} attempt={ev.get('attempt', '?')} "
        f"reason={str(ev.get('reason', '?'))[:50]}"
    )


def _summarize_pipeline_end(ev: dict[str, Any]) -> str:
    return f"done rows={ev.get('rows_total', 0):,} dur={ev.get('duration_s', 0):.1f}s"


_SUMMARIZERS: dict[str, Any] = {
    "pipeline_start": _summarize_pipeline_start,
    "chunk_start": _summarize_chunk_start,
    "chunk_end": _summarize_chunk_end,
    "chunk_error": _summarize_chunk_error,
    "state_end": _summarize_state_end,
    "state_error": _summarize_state_error,
    "retry": _summarize_retry,
    "pipeline_end": _summarize_pipeline_end,
}


def _summarize(ev: dict[str, Any]) -> str:
    """Compress an event dict into a one-line human summary for the recent panel."""
    evt = ev.get("event", "")
    fn = _SUMMARIZERS.get(evt)
    if fn is not None:
        return fn(ev)
    return ", ".join(f"{k}={v}" for k, v in ev.items() if k not in ("ts", "event"))[:80]


# ── ETA computations ─────────────────────────────────────────────────────────


def _states_finished_in_chunk(state: MonitorState) -> int:
    return sum(1 for info in state.states.values() if info["status"] in ("ok", "error"))


def _states_running_in_chunk(state: MonitorState) -> int:
    return sum(1 for info in state.states.values() if info["status"] == "running")


def _median(values: list[float] | deque[float]) -> float | None:
    seq = list(values)
    if not seq:
        return None
    return statistics.median(seq)


def _pipeline_eta(state: MonitorState) -> float | None:
    """Avg of completed chunks times remaining chunks. None until we have data."""
    if state.ended_at:
        return 0.0
    if not state.chunk_durations:
        return None
    remaining = max(0, (state.chunks_total or 0) - state.chunks_done - state.chunks_failed)
    if remaining == 0:
        # All chunks accounted for but no pipeline_end yet — assume imminent.
        return None
    avg = sum(state.chunk_durations) / len(state.chunk_durations)
    eta = remaining * avg
    # Subtract whatever the current chunk has already burned (it's part of remaining).
    if state.active_chunk_started_at:
        eta -= time.time() - state.active_chunk_started_at
    return max(eta, 0.0)


def _chunk_eta(state: MonitorState) -> float | None:
    """Per-chunk ETA from median state duration divided by parallel workers.

    Uses a sliding window so a 240s outlier earlier doesn't poison the
    estimate after SIDRA recovers.
    """
    if not state.active_chunk:
        return None
    median = _median(state.state_durations)
    if median is None:
        return None
    finished = _states_finished_in_chunk(state)
    remaining = max(0, STATES_PER_CHUNK - finished)
    if remaining == 0:
        return 0.0
    # Wall-clock model: 4 workers process states in parallel, so completing
    # `remaining` takes ceil(remaining/4) * median, biased optimistically.
    batches = max(1, (remaining + PARALLEL_STATE_FETCHES - 1) // PARALLEL_STATE_FETCHES)
    return batches * median


def _state_eta(info: dict[str, Any], state: MonitorState, now: float) -> float | None:
    """How long the current running state is *expected* to still take."""
    median = _median(state.state_durations)
    if median is None or "started_at" not in info:
        return None
    elapsed = now - info["started_at"]
    return max(0.0, median - elapsed)


# ── Renderable builders ──────────────────────────────────────────────────────


def _build_header(state: MonitorState, now: float) -> Table:
    started = state.started_at
    elapsed = (state.ended_at or now) - started if started else 0.0
    pipeline_eta = _pipeline_eta(state)

    # Stack: row 1 = identity, row 2 = timers. Two rows beats wrapping in a
    # narrow terminal when ETA gets long (e.g. "elapsed 35m04s   ETA 15m10s").
    head = Table.grid(expand=True)
    head.add_column(ratio=1)
    head.add_row(
        Text.from_markup(
            f"[bold]Pipeline:[/bold] {state.pipeline or '?'}    "
            f"[bold]Run:[/bold] {state.run_id or '?'}"
        )
    )
    head.add_row(
        Text.from_markup(
            f"[dim]elapsed[/dim] [bold]{_fmt_duration(elapsed)}[/bold]    "
            f"[dim]pipeline ETA[/dim] [bold]{_fmt_eta(pipeline_eta)}[/bold]"
        )
    )
    return head


def _build_progress(state: MonitorState, now: float) -> Progress:
    """Stack two progress rows: chunks (overall) + states-within-current-chunk."""
    progress = Progress(
        TextColumn("{task.fields[label]}", justify="right"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TextColumn("{task.fields[extra]}"),
        TimeElapsedColumn(),
        TextColumn("[dim]ETA[/dim] [bold]{task.fields[eta]}[/bold]"),
        expand=True,
    )

    # Row 1: chunks.
    chunks_total = max(state.chunks_total or 1, state.chunks_done + state.chunks_failed)
    progress.add_task(
        "chunks",
        total=chunks_total,
        completed=state.chunks_done + state.chunks_failed,
        label="[bold]Chunks[/bold]",
        extra=(
            f"[dim]rows[/dim] [bold]{state.rows_total:,}[/bold]  "
            f"[dim]retries[/dim] [bold]{state.retries}[/bold]  "
            f"[dim]errors[/dim] [bold red]{state.errors}[/bold red]"
        ),
        eta=_fmt_eta(_pipeline_eta(state)),
    )

    # Row 2: states in current chunk (only meaningful if a chunk is running).
    if state.active_chunk:
        finished = _states_finished_in_chunk(state)
        running = _states_running_in_chunk(state)
        progress.add_task(
            "states",
            total=STATES_PER_CHUNK,
            completed=finished,
            label="[bold]Chunk states[/bold]",
            extra=f"[dim]running[/dim] [bold]{running}[/bold]",
            eta=_fmt_eta(_chunk_eta(state)),
        )

    return progress


def _build_active_line(state: MonitorState, now: float) -> Text:
    if state.active_chunk:
        active_elapsed = now - (state.active_chunk_started_at or now)
        chunk_eta = _chunk_eta(state)
        return Text.from_markup(
            f"[bold]Current chunk:[/bold] {state.active_chunk}  "
            f"[dim]running[/dim] [bold]{_fmt_duration(active_elapsed)}[/bold]  "
            f"[dim]ETA[/dim] [bold]{_fmt_eta(chunk_eta)}[/bold]"
        )
    if state.ended_at:
        return Text.from_markup("[bold green]✓ Pipeline finished[/bold green]")
    return Text("Waiting for next chunk…", style="dim")


def _render_state_running(
    uf: str, info: dict[str, Any], state: MonitorState, now: float, last_seen: float
) -> Text:
    """Cyan ⏳ cell with elapsed + ETA, or yellow STUCK cell if last_seen is stale."""
    elapsed = now - info["started_at"]
    stuck = (now - last_seen) > STUCK_THRESHOLD_S
    if stuck:
        return Text.from_markup(f"[yellow]⏳ {uf}[/yellow]  STUCK {_fmt_duration(elapsed)}")
    eta = _state_eta(info, state, now)
    eta_str = f" ETA {_fmt_duration(eta)}" if eta is not None else ""
    return Text.from_markup(f"[cyan]⏳ {uf}[/cyan]  {_fmt_duration(elapsed)}{eta_str}")


def _render_state_ok(
    uf: str, info: dict[str, Any], state: MonitorState, now: float, last_seen: float
) -> Text:
    """Green ✓ cell with row count + duration."""
    rows = info.get("rows")
    dur = info.get("duration_s")
    rows_str = f"{int(rows):,}" if rows is not None else "?"
    dur_str = f"{dur:.1f}s" if isinstance(dur, int | float) else "?"
    return Text.from_markup(f"[green]✓ {uf}[/green]  [dim]{rows_str} {dur_str}[/dim]")


def _render_state_error(
    uf: str, info: dict[str, Any], state: MonitorState, now: float, last_seen: float
) -> Text:
    """Red ✗ cell with truncated error message."""
    err = str(info.get("error", "?"))[:20]
    return Text.from_markup(f"[red]✗ {uf}[/red]  [dim]{err}[/dim]")


def _render_state_other(
    uf: str, info: dict[str, Any], state: MonitorState, now: float, last_seen: float
) -> Text:
    """Fallback dim cell for unknown/transient statuses."""
    return Text.from_markup(f"[dim]{uf}  {info['status']}[/dim]")


# Status → renderer. Mirrors the dispatch pattern used elsewhere in this module
# (_DIAGNOSIS_PATTERNS, MonitorState._handlers, _SUMMARIZERS). Falls back to
# _render_state_other for any status not listed.
_STATE_RENDERERS: dict[str, Any] = {
    "running": _render_state_running,
    "ok": _render_state_ok,
    "error": _render_state_error,
}


def _render_state_cell(uf: str, info: dict[str, Any], state: MonitorState, now: float) -> Text:
    """Render a single UF cell. Dispatches on ``info['status']``."""
    last_seen = info.get("last_seen") or info.get("started_at") or now
    renderer = _STATE_RENDERERS.get(info["status"], _render_state_other)
    return renderer(uf, info, state, now, last_seen)


def _build_state_grid(state: MonitorState, now: float) -> Table:
    grid = Table.grid(padding=(0, 2))
    for _ in range(4):
        grid.add_column()
    cells = [_render_state_cell(uf, info, state, now) for uf, info in state.states.items()]
    for i in range(0, len(cells), 4):
        grid.add_row(*cells[i : i + 4])
    return grid


def _build_recent_panel(state: MonitorState) -> Panel:
    tail_table = Table.grid(padding=(0, 1))
    tail_table.add_column(width=10, style="dim")
    tail_table.add_column(width=14, style="cyan")
    tail_table.add_column()
    for stamp, evt, summary in state.recent:
        tail_table.add_row(stamp, evt, summary)
    return Panel(tail_table, title="recent events", title_align="left", border_style="dim")


def _build_errors_panel(state: MonitorState) -> Panel | None:
    """One row per recent error: timestamp, scope, message, probable cause."""
    if not state.error_history:
        return None
    table = Table.grid(padding=(0, 1))
    table.add_column(width=10, style="dim")  # ts
    table.add_column(width=6, style="bold")  # scope
    table.add_column(width=10, style="red")  # target
    table.add_column()  # error + cause
    for err in state.error_history:
        stamp = datetime.fromtimestamp(err["ts"], UTC).strftime("%H:%M:%S")
        cause = _diagnose(err["error"])
        message = (
            f"[red]{str(err['error'])[:120]}[/red]\n"
            f"[dim]→ causa provável:[/dim] [yellow]{cause}[/yellow]"
        )
        table.add_row(stamp, err["kind"], err["target"], Text.from_markup(message))
    return Panel(
        table,
        title=f"errors ({len(state.error_history)})",
        title_align="left",
        border_style="red",
    )


def _render(state: MonitorState, log_path: Path) -> Panel:
    now = time.time()
    parts: list[Any] = [
        _build_header(state, now),
        Text(""),
        _build_progress(state, now),
        Text(""),
        _build_active_line(state, now),
        _build_state_grid(state, now),
        Text(""),
        _build_recent_panel(state),
    ]
    errors_panel = _build_errors_panel(state)
    if errors_panel is not None:
        parts.append(errors_panel)
    return Panel(Group(*parts), title=f"embrapa monitor — {log_path.name}", border_style="blue")


# ── Main loop ────────────────────────────────────────────────────────────────


def _tail_jsonl(log_path: Path, last_position: int) -> tuple[list[dict[str, Any]], int]:
    """Read new JSONL events since *last_position*; return (events, new_position).

    Silently skips blank lines and ``json.JSONDecodeError`` lines (matches the
    previous inline behaviour — the monitor must keep rendering even if the
    producer ever writes a torn line). Raises ``FileNotFoundError`` if the log
    disappears mid-run so the caller can break the loop cleanly.
    """
    events: list[dict[str, Any]] = []
    with log_path.open(encoding="utf-8") as f:
        f.seek(last_position)
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
        return events, f.tell()


def run(
    log_path: Path,
    follow: bool = True,
    console: Console | None = None,
    tick_seconds: float = 1.0,
) -> None:
    """Stream events from ``log_path`` and render until pipeline_end / EOF / Ctrl-C.

    The loop re-renders every ``tick_seconds`` regardless of new events so
    elapsed durations and ETAs keep advancing while SIDRA stalls.
    """
    console = console or Console(legacy_windows=False)
    if not log_path.exists():
        console.print(f"[red]Log not found:[/red] {log_path}")
        return

    state = MonitorState()
    last_position = 0

    try:
        with Live(_render(state, log_path), refresh_per_second=4, console=console) as live:
            while True:
                try:
                    events, last_position = _tail_jsonl(log_path, last_position)
                except FileNotFoundError:
                    break
                for ev in events:
                    state.apply(ev)

                live.update(_render(state, log_path))

                if state.ended_at:
                    # Give the user a moment with the final frame before exiting.
                    time.sleep(1.0)
                    break
                if not follow:
                    break
                time.sleep(tick_seconds)
    except KeyboardInterrupt:
        console.print("\n[dim]Monitor stopped.[/dim]")
