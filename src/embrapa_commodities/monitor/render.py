"""Rich UI builders + main tailing loop for the monitor.

Everything in this module is downstream of :mod:`embrapa_commodities.monitor.state`:
it consumes a :class:`MonitorState` and produces Rich renderables (or in the
case of :func:`run`, drives the live update loop). Splitting it out keeps
the rich-free state module unit-testable without pulling in any terminal UI.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

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

from embrapa_commodities.monitor.state import (
    STATES_PER_CHUNK,
    STUCK_THRESHOLD_S,
    MonitorState,
    _chunk_eta,
    _diagnose,
    _fmt_duration,
    _fmt_eta,
    _pipeline_eta,
    _state_eta,
    _states_finished_in_chunk,
    _states_running_in_chunk,
)

# ── Per-status cell renderers ────────────────────────────────────────────


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


# Status → renderer. Mirrors the dispatch pattern used elsewhere in the
# monitor package (_DIAGNOSIS_PATTERNS, MonitorState._handlers, _SUMMARIZERS).
# Falls back to _render_state_other for any status not listed.
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


# ── Renderable builders ──────────────────────────────────────────────────


def _build_state_grid(state: MonitorState, now: float) -> Table:
    grid = Table.grid(padding=(0, 2))
    for _ in range(4):
        grid.add_column()
    cells = [_render_state_cell(uf, info, state, now) for uf, info in state.states.items()]
    for i in range(0, len(cells), 4):
        grid.add_row(*cells[i : i + 4])
    return grid


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
        from datetime import UTC, datetime

        stamp = datetime.fromtimestamp(err["ts"], UTC).strftime("%H:%M:%S")
        cause = _diagnose(err["error"])
        message = (
            f"[red]{str(err['error'])[:120]}[/red]\n"
            f"[dim]→ probable cause:[/dim] [yellow]{cause}[/yellow]"
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


# ── Main loop ────────────────────────────────────────────────────────────


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
