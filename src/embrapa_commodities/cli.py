"""Embrapa commodities CLI — single entry point for local/manual orchestration."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import typer
from google.cloud import bigquery, storage
from rich.console import Console
from rich.table import Table

from embrapa_commodities import backup, discover, doctor, monitor, observability
from embrapa_commodities.bcb import currency as bcb_currency
from embrapa_commodities.bcb import inflation as bcb_inflation
from embrapa_commodities.comex import pipeline as comex_pipeline
from embrapa_commodities.comtrade import pipeline as comtrade_pipeline
from embrapa_commodities.comtrade.client import ComtradeQuotaError
from embrapa_commodities.config import Settings, get_credentials, get_settings
from embrapa_commodities.core import (
    ChunkOutcome,
    ChunkTracker,
    chunked_run,
    pipeline_run,
)
from embrapa_commodities.ibge import pam_pipeline
from embrapa_commodities.ibge import pipeline as ibge_pipeline
from embrapa_commodities.ibge.client import recommended_chunk_years

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)
app = typer.Typer(no_args_is_help=True, add_completion=False, help="Embrapa commodities pipeline")

ingest_app = typer.Typer(no_args_is_help=True, help="Bronze-layer ingestion commands")
app.add_typer(ingest_app, name="ingest")

discover_app = typer.Typer(
    no_args_is_help=True,
    help="Auxiliary lookups — inspect IBGE / BCB before committing codes to .env",
)
app.add_typer(discover_app, name="discover")


# ─── ingest registry ──────────────────────────────────────────────────────────
# ★ The single extension point for `ingest all`. Each @ingest_app.command()
# stays hand-maintained (observability and heterogeneous messages across sources).
# When adding a source: insert an IngestSpec here + an entry in
# doctor.SOURCE_CHECKS / doctor.BRONZE_TARGETS. See
# docs/adding_a_data_source.md.


@dataclass(frozen=True)
class IngestSpec:
    name: str  # subcommand ('ibge', 'bcb-inflation', ...)
    module: ModuleType  # module with .run(settings, **kwargs) -> str
    accepts_full: bool  # True when .run accepts full=bool (delta-aware pipelines)
    label: str  # label shown in `ingest all`
    in_all: bool = True  # False = only runnable via `ingest <name>` (outside the default batch)


# `module` attribute, not a function: spec.module.run(...) does the lookup at
# call time, keeping monkeypatch.setattr(cli.bcb_inflation, "run", ...)
# working (see tests/test_cli.py).
INGESTS: list[IngestSpec] = [
    IngestSpec("ibge", ibge_pipeline, accepts_full=True, label="IBGE PEVS"),
    # PAM is ANNUAL, slow-changing data (~1yr publication lag) and a freshly-shipped
    # source: kept OUT of the nightly `ingest all` (in_all=False) so the live cron
    # path stays unchanged. Runs on demand via `ingest ibge-pam`; give it its own
    # monthly cadence later (like COMTRADE) once validated.
    IngestSpec("ibge-pam", pam_pipeline, accepts_full=True, label="IBGE PAM", in_all=False),
    IngestSpec("bcb-inflation", bcb_inflation, accepts_full=True, label="BCB inflation"),
    IngestSpec("bcb-currency", bcb_currency, accepts_full=True, label="BCB FX"),
    IngestSpec("comex", comex_pipeline, accepts_full=True, label="MDIC COMEX"),
    # COMTRADE stays out of `ingest all`: it is key-gated (RuntimeError without a key) and
    # quota-gated/massive (252 reporters × years) — runs only via `ingest comtrade`.
    IngestSpec("comtrade", comtrade_pipeline, accepts_full=True, label="UN COMTRADE", in_all=False),
]


# ─── chunked-command presentation helpers ──────────────────────────────────────
# The CLI is presentation-only: the per-(flow, year)/(year, batch) loop and its
# continue-on-failure now live in each pipeline's run(); these helpers turn the
# ChunkOutcome stream that run() emits into console lines + the failure summary.
# The observability emit pair / chunks_ok-failed bookkeeping lives in
# core.chunked_run (the ChunkTracker yielded below).


def _echo_chunk_result(tracker: ChunkTracker, outcome: ChunkOutcome) -> None:
    """Print one finished chunk's result line, mirroring its status."""
    duration = tracker.last_duration_s
    cid = outcome.chunk_id
    if outcome.status == "loaded":
        console.print(f"  [green]✓[/green] {cid} → {outcome.destination} [dim]({duration}s)[/dim]")
    elif outcome.status == "skipped":
        console.print(f"  [dim]·[/dim] {cid} — {outcome.detail} [dim](skipped, {duration}s)[/dim]")
    else:
        console.print(f"  [red]✗ {cid} failed:[/red] {outcome.detail[:200]}")


def _make_chunk_handlers(
    tracker: ChunkTracker,
) -> tuple[Callable[[str], None], Callable[[ChunkOutcome], None]]:
    """Build the ``(on_chunk_start, on_chunk)`` callbacks a pipeline ``run`` drives.

    ``on_chunk_start`` emits ``chunk_start`` (via the tracker) and prints the
    ``[i/total] -> chunk_id`` heading; ``on_chunk`` emits ``chunk_end`` /
    ``chunk_error`` (via the tracker) and prints the result line.
    """

    def on_chunk_start(chunk_id: str) -> None:
        i = tracker.start_chunk(chunk_id)
        console.print(f"  [dim][{i}/{tracker.total}][/dim] [bold]-> {chunk_id}[/bold]")

    def on_chunk(outcome: ChunkOutcome) -> None:
        tracker.finish(outcome)
        _echo_chunk_result(tracker, outcome)

    return on_chunk_start, on_chunk


def _summarize_and_exit(
    tracker: ChunkTracker, *, label: str, success_msg: str, retry_hint: str = ""
) -> None:
    """Print the run's closing summary and exit non-zero if any chunk failed.

    Shared tail of every chunked command so the failure listing and exit code
    are identical across sources; ``retry_hint`` carries the source-specific
    "how to re-run" line (empty to omit).
    """
    if tracker.chunks_failed:
        console.print(
            f"\n[yellow bold]⚠ {len(tracker.chunks_failed)} {label} chunk(s) failed; "
            f"{len(tracker.chunks_ok)} succeeded[/yellow bold]"
        )
        for chunk_id, err in tracker.chunks_failed:
            console.print(f"  [red]✗[/red] {chunk_id} — {err}")
        if retry_hint:
            console.print(retry_hint)
        raise typer.Exit(code=1)
    console.print(success_msg)


# ─── ingest ───────────────────────────────────────────────────────────────────
@ingest_app.command("ibge")
def ingest_ibge(
    full: bool = typer.Option(
        False,
        "--full",
        help="Re-fetch the whole IBGE_START_YEAR→END window (default is delta: recent years only).",
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Rebuild Bronze from the archived raw SIDRA response(s), without re-querying SIDRA.",
    ),
) -> None:
    """Ingest IBGE PEVS into the configured Bronze table (extract→raw→bronze)."""
    settings = get_settings()
    with pipeline_run(
        "ibge",
        params={
            "start_year": settings.ibge_start_year,
            "end_year": settings.ibge_end_year,
            "products": settings.product_codes,
            "full": full,
            "from_raw": from_raw,
        },
    ) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = ibge_pipeline.run(settings, full=full, from_raw=from_raw)
    if destination:
        console.print(f"[green]✓[/green] IBGE bronze loaded → {destination}")
    else:
        console.print(
            "[yellow]⚠ IBGE ingest skipped:[/yellow] SIDRA returned no new rows. "
            "On a delta run Bronze is likely already current; on --full, lower "
            "IBGE_END_YEAR in .env to the latest published year."
        )


@ingest_app.command("ibge-pam")
def ingest_ibge_pam(
    full: bool = typer.Option(
        False,
        "--full",
        help="Re-fetch the whole PAM_START_YEAR→END window (default is delta: recent years only).",
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Rebuild Bronze from the archived raw SIDRA response(s), without re-querying SIDRA.",
    ),
) -> None:
    """Ingest IBGE PAM (Produção Agrícola Municipal) into Bronze (extract→raw→bronze)."""
    settings = get_settings()
    with pipeline_run(
        "ibge-pam",
        params={
            "start_year": settings.pam_start_year,
            "end_year": settings.pam_end_year,
            "products": settings.pam_product_codes_list,
            "full": full,
            "from_raw": from_raw,
        },
    ) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = pam_pipeline.run(settings, full=full, from_raw=from_raw)
    if destination:
        console.print(f"[green]✓[/green] IBGE PAM bronze loaded → {destination}")
    else:
        console.print(
            "[yellow]⚠ IBGE PAM ingest skipped:[/yellow] SIDRA returned no new rows. "
            "On a delta run Bronze is likely already current; on --full, lower "
            "PAM_END_YEAR in .env to the latest published year."
        )


@ingest_app.command("bcb-inflation")
def ingest_bcb_inflation(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force a full refetch from BCB_START_YEAR. Default is delta-from-last-load.",
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Rebuild Bronze from the archived raw SGS trail, without re-fetching the API.",
    ),
) -> None:
    """Ingest configured BCB SGS inflation series (extract→raw→bronze)."""
    settings = get_settings()
    with pipeline_run("bcb-inflation", params={"full": full, "from_raw": from_raw}) as (
        _run_id,
        log_path,
    ):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = bcb_inflation.run(settings, full=full, from_raw=from_raw)
    if destination:
        console.print(f"[green]✓[/green] BCB inflation bronze loaded → {destination}")
    else:
        console.print("[dim]BCB inflation: nothing new since last ingest.[/dim]")


@ingest_app.command("bcb-currency")
def ingest_bcb_currency(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force a full refetch from BCB_START_YEAR. Default is delta-from-last-load.",
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Rebuild Bronze from the archived raw SGS trail, without re-fetching the API.",
    ),
) -> None:
    """Ingest configured BCB SGS FX series (extract→raw→bronze)."""
    settings = get_settings()
    with pipeline_run("bcb-currency", params={"full": full, "from_raw": from_raw}) as (
        _run_id,
        log_path,
    ):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = bcb_currency.run(settings, full=full, from_raw=from_raw)
    if destination:
        console.print(f"[green]✓[/green] BCB currency bronze loaded → {destination}")
    else:
        console.print("[dim]BCB currency: nothing new since last ingest.[/dim]")


def _ibge_batch_ingest(settings: Settings, chunk_years: int | None) -> ChunkTracker:
    """Ingest the full IBGE window in year chunks (each a ``full=True`` load).

    Shared by ``ingest ibge-batch`` and ``ingest reconcile``. It owns the
    chunked loop + continue-on-failure and returns the populated ChunkTracker
    so each caller decides how to summarize/exit: ``ibge-batch`` exits non-zero
    on any failed chunk, whereas ``reconcile`` records the failure and moves on
    to the BCB/COMEX legs. Chunking (vs the single-shot ``ibge --full``) is what
    keeps the huge 1986→today SIDRA pull under the unattended slow-byte deadline.
    """
    if settings.ibge_start_year is None:
        raise typer.BadParameter("Set IBGE_START_YEAR in .env before running batch ingest.")

    n_products = len(settings.product_codes)
    if chunk_years is None:
        chunk_years = recommended_chunk_years(n_products)
        chunk_source = f"auto (for {n_products} product(s))"
    else:
        chunk_source = "manual override"

    # Snapshot originals before the loop — we mutate settings each iteration.
    range_start = settings.ibge_start_year
    range_end = settings.ibge_end_year

    chunks = list(range(range_start, range_end + 1, chunk_years))
    total = len(chunks)
    console.print(
        f"[bold]IBGE batch ingest:[/bold] {range_start}-{range_end} "
        f"in {total} chunk(s) of {chunk_years} year(s) [dim]({chunk_source})[/dim]"
    )

    # Build clients once; reuse across all chunks to avoid repeated auth.
    creds = get_credentials(settings)
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )

    # ibge-batch drives its own per-chunk loop (each chunk is a year-range that
    # calls ibge_pipeline.run with full=True); chunked_run owns the event
    # scaffold + ok/failed bookkeeping, matching comex/comtrade.
    params = {
        "start_year": range_start,
        "end_year": range_end,
        "chunk_years": chunk_years,
        "products": settings.product_codes,
    }
    with chunked_run("ibge-batch", total=total, params=params) as tracker:
        console.print(f"[dim]event log:[/dim] {tracker.log_path}")
        console.print(
            "[dim]tip:[/dim] run [bold]uv run embrapa monitor[/bold] in another terminal "
            "to watch progress live"
        )
        for chunk_start in chunks:
            chunk_end = min(chunk_start + chunk_years - 1, range_end)
            chunk_id = f"{chunk_start}-{chunk_end}"
            chunk_settings = settings.model_copy(
                update={"ibge_start_year": chunk_start, "ibge_end_year": chunk_end}
            )
            i = tracker.start_chunk(chunk_id)
            console.print(f"  [dim][{i}/{total}][/dim] [bold]-> {chunk_id}[/bold]")
            try:
                destination = ibge_pipeline.run(
                    chunk_settings,
                    full=True,
                    storage_client=storage_client,
                    bq_client=bq_client,
                )
            except Exception as exc:
                # Continue-on-failure: a single hung chunk must not strand the
                # rest; the chunk_error event + summary point at the year ranges
                # that need a re-run.
                outcome = ChunkOutcome(chunk_id, "failed", detail=str(exc))
            else:
                outcome = (
                    ChunkOutcome(chunk_id, "loaded", destination=destination)
                    if destination
                    else ChunkOutcome(chunk_id, "skipped", detail="SIDRA returned no rows")
                )
            tracker.finish(outcome)
            _echo_chunk_result(tracker, outcome)

    return tracker


@ingest_app.command("ibge-batch")
def ingest_ibge_batch(
    chunk_years: int | None = typer.Option(
        None,
        "--chunk-years",
        "-c",
        help=(
            "Years per batch. If omitted, auto-computed from the number of "
            "products in IBGE_PRODUCT_CODES so every state response stays "
            "under SIDRA's cell limit with a safety margin."
        ),
        min=1,  # 0 → empty range (silent no-op); negative → ValueError. Reject both.
    ),
) -> None:
    """Ingest IBGE PEVS in year-chunked batches to avoid IBGE connection drops.

    For historical windows (>10 years), the IBGE API occasionally closes
    large connections mid-transfer. This command splits the full window
    defined by IBGE_START_YEAR / IBGE_END_YEAR into chunks and runs them
    sequentially, each as a separate Bronze load (WRITE_APPEND).

    Chunk size auto-scales with the number of products: more products means
    smaller chunks (since SIDRA's cell limit is fixed per request).
    """
    settings = get_settings()
    tracker = _ibge_batch_ingest(settings, chunk_years)
    _summarize_and_exit(
        tracker,
        label="IBGE",
        success_msg=f"\n[green bold]✓ All {tracker.total} batches complete[/green bold]",
        retry_hint=(
            "\n[dim]Re-run failed chunks individually with:[/dim]\n"
            "  IBGE_START_YEAR=<start> IBGE_END_YEAR=<end> uv run embrapa ingest ibge"
        ),
    )


@ingest_app.command("comex")
def ingest_comex(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force re-download of every (flow, year) file, ignoring the ETag "
        "freshness check. Default re-downloads only files the source changed.",
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Skip the download phase entirely and rebuild Bronze from the raw "
        "Parquet already in GCS — re-filter / apply new products without internet.",
    ),
) -> None:
    """Ingest MDIC Comex Stat flows (export + import) via the two-phase raw zone.

    Per (flow, year): Phase 1 archives the verbatim CSV→Parquet to the GCS raw
    zone (only when the source ETag changed), Phase 2 filters it to the
    configured NCMs and loads Bronze. Emits a chunk per (flow, year) for live
    `embrapa monitor` progress.
    """
    settings = get_settings()
    creds = get_credentials(settings)
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    total = len(comex_pipeline.all_chunks(settings))
    mode = "from-raw" if from_raw else ("full" if full else "delta")
    params = {"full": full, "from_raw": from_raw, "flows": settings.comex_flows_list}

    # The (flow, year) loop + continue-on-failure live in comex_pipeline.run; the
    # CLI only presents it. chunked_run owns the event scaffold; run() drives the
    # tracker via the start/finish callbacks.
    with chunked_run("comex", total=total, params=params) as tracker:
        console.print(f"[dim]event log:[/dim] {tracker.log_path}")
        console.print(f"[bold]COMEX ingest:[/bold] {total} chunk(s) [dim]({mode})[/dim]")
        on_chunk_start, on_chunk = _make_chunk_handlers(tracker)
        comex_pipeline.run(
            settings,
            full=full,
            from_raw=from_raw,
            storage_client=storage_client,
            bq_client=bq_client,
            on_chunk_start=on_chunk_start,
            on_chunk=on_chunk,
        )

    _summarize_and_exit(
        tracker,
        label="COMEX",
        success_msg=f"\n[green bold]✓ All {total} COMEX chunk(s) complete[/green bold]",
    )


@ingest_app.command("comtrade")
def ingest_comtrade(
    full: bool = typer.Option(
        False, "--full", help="Re-fetch every (year, reporter-batch) chunk, ignoring resume."
    ),
    from_raw: bool = typer.Option(
        False,
        "--from-raw",
        help="Rebuild Bronze from the archived raw chunks, without calling the API.",
    ),
) -> None:
    """Ingest UN Comtrade global flows into Bronze, chunked by (year, reporter-batch).

    Resumable: a re-run fetches only chunks not yet archived (+ the latest year).
    If the daily API quota runs out mid-run, stop and re-run later — no lost work.
    """
    settings = get_settings()
    if not settings.comtrade_api_key:
        console.print(
            "[red]COMTRADE_API_KEY is empty.[/red] Set it in .env "
            "(free key from comtradedeveloper.un.org)."
        )
        raise typer.Exit(code=1)
    creds = get_credentials(settings)
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )
    # Resolve reporters once (here, for the header count) — run() resolves them
    # again from the same resolve_reporters(), so the two never drift.
    reporters = comtrade_pipeline.resolve_reporters(settings)
    total = len(comtrade_pipeline.plan_chunks(settings, reporters))
    mode = "from-raw" if from_raw else ("full" if full else "resume")

    # The (year, reporter-batch) loop, continue-on-failure, and stop-on-quota all
    # live in comtrade_pipeline.run; the CLI presents the ChunkOutcome stream.
    quota_hit = False
    with chunked_run("comtrade", total=total) as tracker:
        console.print(f"[dim]event log:[/dim] {tracker.log_path}")
        console.print(
            f"[bold]COMTRADE ingest:[/bold] {total} chunk(s) "
            f"[dim]({mode}, {len(reporters)} reporters)[/dim]"
        )
        on_chunk_start, on_chunk = _make_chunk_handlers(tracker)
        try:
            comtrade_pipeline.run(
                settings,
                full=full,
                from_raw=from_raw,
                storage_client=storage_client,
                bq_client=bq_client,
                on_chunk_start=on_chunk_start,
                on_chunk=on_chunk,
            )
        except ComtradeQuotaError as exc:
            # Daily quota exhausted mid-run — stop cleanly; re-running resumes
            # from the un-archived chunks. (pipeline_end still emits on __exit__.)
            quota_hit = True
            console.print(
                f"\n[yellow bold]⚠ COMTRADE quota exhausted[/yellow bold] [dim]({exc})[/dim]\n"
                "[dim]Re-run to resume — archived chunks are skipped.[/dim]"
            )

    if quota_hit:
        raise typer.Exit(code=1)
    _summarize_and_exit(
        tracker,
        label="COMTRADE",
        success_msg=f"\n[green bold]✓ All {total} COMTRADE chunk(s) complete[/green bold]",
        retry_hint="[dim](quota? rate limit? re-run to resume — archived chunks are skipped)[/dim]",
    )


@ingest_app.command("all")
def ingest_all(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force full refetch on delta-aware pipelines (whole windows, not just the delta).",
    ),
) -> None:
    """Run every registered Bronze pipeline sequentially in INGESTS order.

    Continue-on-failure at the *source* level, mirroring the per-chunk policy
    inside each pipeline: a source that raises (a hard error, or an aggregated
    ``IngestPartialFailure`` from its own chunk loop) is recorded and the next
    source still runs. The blind nightly cron thus never aborts the whole batch
    on one source's transient trouble. A non-zero exit at the end reports that
    at least one source failed.
    """
    settings = get_settings()
    failures: list[tuple[str, str]] = []
    for spec in INGESTS:
        if not spec.in_all:
            continue
        console.print(f"[bold]→ {spec.label}[/bold]")
        kwargs = {"full": full} if spec.accepts_full else {}
        # Wrap each pipeline in the same observability lifecycle the individual
        # `ingest <source>` commands use, so `ingest all` shows up in
        # `embrapa monitor` and a mid-batch failure leaves a chunk_error in the
        # event log instead of running completely silent.
        try:
            with pipeline_run(spec.name, params=kwargs) as (_run_id, log_path):
                console.print(f"[dim]event log:[/dim] {log_path}")
                spec.module.run(settings, **kwargs)
        except Exception as exc:
            failures.append((spec.label, str(exc)[:200]))
            console.print(f"[red]✗ {spec.label} failed:[/red] {str(exc)[:200]}")

    if failures:
        console.print(f"\n[yellow bold]⚠ {len(failures)} source(s) failed[/yellow bold]")
        for label, err in failures:
            console.print(f"  [red]✗[/red] {label} — {err}")
        raise typer.Exit(code=1)
    console.print("[green bold]✓ All Bronze pipelines completed[/green bold]")


@ingest_app.command("reconcile")
def ingest_reconcile(
    chunk_years: int | None = typer.Option(
        None,
        "--chunk-years",
        "-c",
        help="IBGE years per batch (see `ingest ibge-batch`). Omit to auto-size to the cell limit.",
        min=1,  # reject 0 (silent no-op) / negative (ValueError) — same as ibge-batch.
    ),
) -> None:
    """Full re-download of every nightly source — the deliberate escape hatch.

    Unlike the nightly delta (which only revisits a recent window), reconcile
    IGNORES each source's delta/ETag short-circuit and re-fetches the WHOLE
    configured history. That is what catches an upstream CORRECTION to an old
    year — e.g. IBGE revising a 1999 PEVS value — which the delta would never
    re-query, and it also force-unsticks a source frozen for any reason.

    Per source: IBGE runs year-CHUNKED (like `ibge-batch`, so the huge
    1986→today SIDRA pull survives an unattended slow-byte deadline); BCB
    inflation/FX and COMEX run with `--full`. COMTRADE is excluded (key-gated),
    exactly like `ingest all`. Continue-on-failure at the source level.

    Bronze only — run `dbt build` afterward to propagate the refreshed Bronze to
    Silver/Gold (`make reconcile` chains both). The incremental Silver is
    year-agnostic (it re-scans whatever Bronze years got a newer
    ingestion_timestamp, of any age), so a plain `dbt build` carries an old-year
    revision all the way to Gold — no `--full-refresh` needed.
    """
    settings = get_settings()
    failures: list[tuple[str, str]] = []

    # IBGE: chunked full window (not the single-shot `ibge --full`) so the huge
    # 1986→today SIDRA pull survives the unattended slow-byte deadline. A
    # BadParameter (IBGE_START_YEAR unset) is a real misconfig — let it abort.
    console.print("[bold]→ IBGE PEVS[/bold] [dim](chunked full window)[/dim]")
    try:
        tracker = _ibge_batch_ingest(settings, chunk_years)
    except typer.BadParameter:
        raise
    except Exception as exc:
        failures.append(("IBGE PEVS", str(exc)[:200]))
        console.print(f"[red]✗ IBGE PEVS failed:[/red] {str(exc)[:200]}")
    else:
        if tracker.chunks_failed:
            failures.append(("IBGE PEVS", f"{len(tracker.chunks_failed)} chunk(s) failed"))

    # BCB inflation/FX + COMEX: --full re-fetches each one's whole configured
    # window. Reuse the same INGESTS registry as `ingest all`, skipping IBGE
    # (already done, chunked) and the out-of-`all` COMTRADE. Gate on
    # accepts_full exactly like `ingest all` so a future non-delta source added
    # to the batch wouldn't trip on an unexpected full= kwarg.
    for spec in INGESTS:
        if not spec.in_all or spec.name == "ibge":
            continue
        kwargs = {"full": True} if spec.accepts_full else {}
        console.print(f"[bold]→ {spec.label}[/bold] [dim](full)[/dim]")
        try:
            with pipeline_run(spec.name, params=kwargs) as (_run_id, log_path):
                console.print(f"[dim]event log:[/dim] {log_path}")
                spec.module.run(settings, **kwargs)
        except Exception as exc:
            failures.append((spec.label, str(exc)[:200]))
            console.print(f"[red]✗ {spec.label} failed:[/red] {str(exc)[:200]}")

    if failures:
        console.print(f"\n[yellow bold]⚠ {len(failures)} source(s) failed[/yellow bold]")
        for label, err in failures:
            console.print(f"  [red]✗[/red] {label} — {err}")
        raise typer.Exit(code=1)
    console.print("[green bold]✓ Reconcile complete — every source fully re-ingested[/green bold]")
    console.print(
        "[dim]Next:[/dim] run [bold]dbt build[/bold] to propagate any revisions to Silver/Gold "
        "[dim](`make reconcile` chains it for you)[/dim]."
    )


# ─── discover ─────────────────────────────────────────────────────────────────
@discover_app.command("ibge-products")
def discover_ibge_products(
    keywords: str = typer.Option(..., "--keywords", "-k", help="Comma-separated keywords"),
    table_id: str = typer.Option("289", "--table-id", "-t"),
) -> None:
    """Search SIDRA classifications for products matching free-text keywords."""
    needles = [k.strip() for k in keywords.split(",") if k.strip()]
    matches = discover.search_ibge_products(table_id, needles)
    if not matches:
        console.print(f"[yellow]No products in table {table_id} matched {needles}[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title=f"IBGE table {table_id} — products matching {needles}")
    table.add_column("Classification", style="dim")
    table.add_column("Code", style="cyan")
    table.add_column("Name")
    for m in matches:
        table.add_row(m.classification_id, m.code, m.name)
    console.print(table)
    console.print(
        f"\n[dim]Suggested .env value:[/dim] IBGE_PRODUCT_CODES={','.join(m.code for m in matches)}"
    )


@discover_app.command("ibge-periods")
def discover_ibge_periods(
    table_id: str = typer.Option("289", "--table-id", "-t"),
) -> None:
    """List every year for which the SIDRA table has data."""
    years = discover.list_ibge_periods(table_id)
    if not years:
        console.print(f"[yellow]Table {table_id} returned no periods.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[bold]Table {table_id}[/bold] — {len(years)} years available")
    console.print(f"  First: [green]{years[0]}[/green]   Last: [green]{years[-1]}[/green]")
    console.print(
        f"[dim]Suggested .env:[/dim] IBGE_START_YEAR={years[0]} IBGE_END_YEAR={years[-1]}"
    )


@discover_app.command("bcb-series")
def discover_bcb_series(
    code: str = typer.Argument(..., help="SGS series code (e.g. 433)"),
    n: int = typer.Option(5, "--last", "-n", help="Number of latest observations to fetch"),
) -> None:
    """Validate an SGS code by printing the most recent N observations."""
    sample = discover.sample_bcb_series(code, n=n)
    if not sample.sample:
        console.print(f"[yellow]Series {code} returned no data.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[bold]SGS series {code}[/bold] — last {len(sample.sample)} observations")
    console.print(json.dumps(sample.sample, indent=2, ensure_ascii=False))


# ─── monitor ──────────────────────────────────────────────────────────────────
@app.command("monitor")
def monitor_cmd(
    log_path: Path | None = typer.Argument(  # noqa: B008
        None,
        help="Path to a JSONL event log. Defaults to the most recent one.",
    ),
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        "-p",
        help="Filter latest-log lookup to a pipeline name (e.g. 'ibge', 'ibge-batch').",
    ),
    no_follow: bool = typer.Option(
        False, "--no-follow", help="Render once over a finished log and exit."
    ),
    list_logs: bool = typer.Option(
        False, "--list", help="List available run logs sorted newest first, then exit."
    ),
) -> None:
    """Live progress dashboard for an ongoing or finished ingest run.

    Examples:
        embrapa monitor                              # tail latest run
        embrapa monitor --pipeline ibge-batch        # tail latest batch run
        embrapa monitor ~/.embrapa/logs/ibge-XXX.jsonl
        embrapa monitor --list                       # show available runs
    """
    if list_logs:
        paths = observability.list_log_paths()
        if not paths:
            console.print(f"[dim]No event logs in {observability.log_dir()}[/dim]")
            return
        table = Table(title="Run logs (newest first)")
        table.add_column("Modified", style="dim")
        table.add_column("Size", justify="right", style="dim")
        table.add_column("Path")
        for p in paths[:30]:
            stat = p.stat()
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
            size_kb = f"{stat.st_size / 1024:.1f} KB"
            table.add_row(mtime, size_kb, str(p))
        console.print(table)
        return

    target = log_path or observability.latest_log_path(pipeline)
    if target is None:
        console.print(
            f"[yellow]No event logs found in {observability.log_dir()}.[/yellow]\n"
            "[dim]Run an ingest first, or pass a path explicitly.[/dim]"
        )
        raise typer.Exit(code=1)
    console.print(f"[dim]Watching:[/dim] {target}")
    monitor.run(target, follow=not no_follow, console=console)


# ─── doctor ───────────────────────────────────────────────────────────────────
@app.command("doctor")
def doctor_cmd() -> None:
    """Quick health-check before running an ingest. ~10 seconds.

    Validates: .env parsing, ADC credentials, BigQuery / GCS reachability,
    IBGE SIDRA + BCB SGS connectivity, and whether Bronze tables exist yet.

    Exits 1 if any check fails (Bronze-tables check is informational).
    """
    results = doctor.run_all()
    table = Table(title="embrapa doctor", show_lines=False)
    table.add_column("", width=3)
    table.add_column("Check", style="bold")
    table.add_column("Detail")
    failed = 0
    for r in results:
        mark = "[green]✓[/green]" if r.ok else "[red]✗[/red]"
        if not r.ok:
            failed += 1
        table.add_row(mark, r.name, r.detail)
    console.print(table)
    if failed:
        console.print(f"[red bold]{failed} check(s) failed[/red bold]")
        raise typer.Exit(code=1)
    console.print("[green bold]All checks passed[/green bold]")


# ─── backup ───────────────────────────────────────────────────────────────────
@app.command("backup-gold")
def backup_gold() -> None:
    """Snapshot prod Gold tables to GCS as Parquet (manual cold-storage).

    Lands at ``gs://${GCS_BUCKET}/backups/run=<ts>/<table>/<table>-*.parquet``.
    GCS lifecycle (versioning + Nearline/Coldline/Archive transitions) handles
    long-term retention without extra config.

    Run after a successful ``make dbt-build-prod`` you want to preserve.
    """
    settings = get_settings()
    run_id, uris = backup.run(settings)
    console.print(f"[green]✓[/green] Gold backup complete  [dim]run_id={run_id}[/dim]")
    for uri in uris:
        console.print(f"  → {uri}")


# ─── dbt passthrough ──────────────────────────────────────────────────────────
@app.command("dbt")
def dbt_passthrough(
    args: list[str] = typer.Argument(None, help="Arguments forwarded to dbt"),  # noqa: B008
) -> None:
    """Forward arbitrary args to `dbt` from inside the dbt/ project dir."""
    dbt_dir = Path(__file__).resolve().parents[2] / "dbt"
    # Use the venv's interpreter so we never resolve a system `dbt` that
    # might be on PATH with a different version.
    cmd = [sys.executable, "-m", "dbt.cli.main", *(args or ["--help"])]
    console.print(f"[dim]$ {' '.join(cmd)} (cwd={dbt_dir})[/dim]")
    result = subprocess.run(cmd, cwd=dbt_dir, check=False)
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
