"""Embrapa commodities CLI — single entry point for local/manual orchestration."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
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
from embrapa_commodities.config import get_credentials, get_settings
from embrapa_commodities.core import pipeline_run
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
# ★ Único ponto de extensão para `ingest all`. Cada @ingest_app.command()
# permanece manuscrito (observabilidade e mensagens heterogêneas entre fontes).
# Quando adicionar uma fonte: insira IngestSpec aqui + entry em
# doctor.SOURCE_CHECKS / doctor.BRONZE_TARGETS. Veja
# docs/adding_a_data_source.md.


@dataclass(frozen=True)
class IngestSpec:
    name: str  # subcomando ('ibge', 'bcb-inflation', ...)
    module: ModuleType  # módulo com .run(settings, **kwargs) -> str
    accepts_full: bool  # True quando .run aceita full=bool (pipelines delta-aware)
    label: str  # rótulo exibido em `ingest all`


# Atributo `module`, não função: spec.module.run(...) faz lookup em tempo de
# chamada, mantendo monkeypatch.setattr(cli.bcb_inflation, "run", ...)
# funcional (ver tests/test_cli.py).
INGESTS: list[IngestSpec] = [
    IngestSpec("ibge", ibge_pipeline, accepts_full=False, label="IBGE PEVS"),
    IngestSpec("bcb-inflation", bcb_inflation, accepts_full=True, label="BCB inflação"),
    IngestSpec("bcb-currency", bcb_currency, accepts_full=True, label="BCB câmbio"),
    IngestSpec("comex", comex_pipeline, accepts_full=True, label="MDIC COMEX"),
]


# ─── ingest ───────────────────────────────────────────────────────────────────
@ingest_app.command("ibge")
def ingest_ibge() -> None:
    """Ingest IBGE PEVS into the configured Bronze table."""
    settings = get_settings()
    with pipeline_run(
        "ibge",
        params={
            "start_year": settings.ibge_start_year,
            "end_year": settings.ibge_end_year,
            "products": settings.product_codes,
        },
    ) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = ibge_pipeline.run(settings)
    if destination:
        console.print(f"[green]✓[/green] IBGE bronze loaded → {destination}")
    else:
        console.print(
            f"[yellow]⚠ IBGE ingest skipped:[/yellow] SIDRA returned no rows for "
            f"{settings.ibge_start_year}-{settings.ibge_end_year}. "
            "Lower IBGE_END_YEAR in .env to the latest published year."
        )


@ingest_app.command("bcb-inflation")
def ingest_bcb_inflation(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force a full refetch from BCB_START_YEAR. Default is delta-from-last-load.",
    ),
) -> None:
    """Ingest configured BCB SGS inflation series."""
    settings = get_settings()
    with pipeline_run("bcb-inflation", params={"full": full}) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = bcb_inflation.run(settings, full=full)
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
) -> None:
    """Ingest configured BCB SGS FX series."""
    settings = get_settings()
    with pipeline_run("bcb-currency", params={"full": full}) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = bcb_currency.run(settings, full=full)
    if destination:
        console.print(f"[green]✓[/green] BCB currency bronze loaded → {destination}")
    else:
        console.print("[dim]BCB currency: nothing new since last ingest.[/dim]")


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

    run_id, log_path = observability.init_run("ibge-batch")
    console.print(f"[dim]event log:[/dim] {log_path}")
    console.print(
        "[dim]tip:[/dim] run [bold]uv run embrapa monitor[/bold] in another terminal "
        "to watch progress live"
    )
    observability.emit(
        "pipeline_start",
        pipeline="ibge-batch",
        run_id=run_id,
        chunks_total=total,
        params={
            "start_year": range_start,
            "end_year": range_end,
            "chunk_years": chunk_years,
            "products": settings.product_codes,
        },
    )

    # Build clients once; reuse across all chunks to avoid repeated auth.
    creds = get_credentials(settings)
    storage_client = storage.Client(project=settings.gcp_project_id, credentials=creds)
    bq_client = bigquery.Client(
        project=settings.gcp_project_id, location=settings.bq_location, credentials=creds
    )

    pipeline_started = time.monotonic()
    chunks_ok: list[str] = []
    chunks_failed: list[tuple[str, str]] = []

    for i, chunk_start in enumerate(chunks, 1):
        chunk_end = min(chunk_start + chunk_years - 1, range_end)
        chunk_id = f"{chunk_start}-{chunk_end}"
        chunk_settings = settings.model_copy(
            update={"ibge_start_year": chunk_start, "ibge_end_year": chunk_end}
        )
        observability.emit("chunk_start", chunk_id=chunk_id, chunk_n=i, chunk_total=total)
        chunk_started = time.monotonic()
        console.print(f"  [dim][{i}/{total}][/dim] [bold]-> {chunk_id}[/bold]")
        try:
            destination = ibge_pipeline.run(
                chunk_settings,
                storage_client=storage_client,
                bq_client=bq_client,
            )
            duration = round(time.monotonic() - chunk_started, 2)
            observability.emit(
                "chunk_end",
                chunk_id=chunk_id,
                chunk_n=i,
                chunk_total=total,
                duration_s=duration,
                destination=destination,
            )
            chunks_ok.append(chunk_id)
            if destination:
                console.print(f"  [green]✓[/green] loaded → {destination} [dim]({duration}s)[/dim]")
            else:
                console.print(
                    f"  [yellow]⚠[/yellow] {chunk_id} — SIDRA returned no rows "
                    f"[dim](skipped, {duration}s)[/dim]"
                )
        except Exception as exc:
            # Continue-on-failure: a single hung chunk should not strand the rest.
            # The chunk_error event in the log + the summary below tell the user
            # exactly which year ranges need a re-run.
            duration = round(time.monotonic() - chunk_started, 2)
            observability.emit(
                "chunk_error",
                chunk_id=chunk_id,
                chunk_n=i,
                chunk_total=total,
                duration_s=duration,
                error=str(exc)[:300],
            )
            chunks_failed.append((chunk_id, str(exc)[:200]))
            console.print(f"  [red]✗ {chunk_id} failed:[/red] {str(exc)[:200]}")

    observability.emit(
        "pipeline_end",
        duration_s=round(time.monotonic() - pipeline_started, 2),
        chunks_ok=len(chunks_ok),
        chunks_failed=len(chunks_failed),
    )

    if chunks_failed:
        console.print(
            f"\n[yellow bold]⚠ {len(chunks_failed)} chunk(s) failed; "
            f"{len(chunks_ok)} succeeded[/yellow bold]"
        )
        for chunk_id, err in chunks_failed:
            console.print(f"  [red]✗[/red] {chunk_id} — {err}")
        console.print(
            "\n[dim]Re-run failed chunks individually with:[/dim]\n"
            "  IBGE_START_YEAR=<start> IBGE_END_YEAR=<end> uv run embrapa ingest ibge"
        )
        raise typer.Exit(code=1)
    console.print(f"\n[green bold]✓ All {total} batches complete[/green bold]")


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
    table_fqn = comex_pipeline.ensure_destination(settings, bq_client)
    chunks = comex_pipeline.all_chunks(settings)
    total = len(chunks)

    mode = "from-raw" if from_raw else ("full" if full else "delta")
    run_id, log_path = observability.init_run("comex")
    console.print(f"[dim]event log:[/dim] {log_path}")
    console.print(f"[bold]COMEX ingest:[/bold] {total} chunk(s) [dim]({mode})[/dim]")
    observability.emit(
        "pipeline_start",
        pipeline="comex",
        run_id=run_id,
        chunks_total=total,
        params={"full": full, "from_raw": from_raw, "flows": settings.comex_flows_list},
    )

    chunks_ok: list[str] = []
    chunks_failed: list[tuple[str, str]] = []
    pipeline_started = time.monotonic()

    for i, (flow, year) in enumerate(chunks, 1):
        chunk_id = comex_pipeline._basename(flow, year)
        observability.emit("chunk_start", chunk_id=chunk_id, chunk_n=i, chunk_total=total)
        chunk_started = time.monotonic()
        console.print(f"  [dim][{i}/{total}][/dim] [bold]-> {chunk_id}[/bold]")
        try:
            if from_raw:
                process = comex_pipeline.has_raw(
                    settings, flow, year, storage_client=storage_client
                )
            else:
                process = comex_pipeline.sync_raw(
                    settings, flow, year, storage_client=storage_client, force=full
                )
            destination = (
                comex_pipeline.bronze_one(
                    settings,
                    flow,
                    year,
                    storage_client=storage_client,
                    bq_client=bq_client,
                    table_fqn=table_fqn,
                )
                if process
                else ""
            )
            duration = round(time.monotonic() - chunk_started, 2)
            observability.emit(
                "chunk_end",
                chunk_id=chunk_id,
                chunk_n=i,
                chunk_total=total,
                duration_s=duration,
                destination=destination,
            )
            chunks_ok.append(chunk_id)
            if destination:
                console.print(f"  [green]✓[/green] loaded → {destination} [dim]({duration}s)[/dim]")
            elif not process:
                console.print(
                    f"  [dim]·[/dim] {chunk_id} — source unchanged "
                    f"[dim](skipped, {duration}s)[/dim]"
                )
            else:
                console.print(
                    f"  [yellow]⚠[/yellow] {chunk_id} — no configured products "
                    f"[dim](skipped, {duration}s)[/dim]"
                )
        except Exception as exc:
            # Continue-on-failure: one bad year (e.g. a 404 for an unpublished
            # file) shouldn't strand the rest. The chunk_error + summary tell
            # the user which (flow, year) to re-run.
            duration = round(time.monotonic() - chunk_started, 2)
            observability.emit(
                "chunk_error",
                chunk_id=chunk_id,
                chunk_n=i,
                chunk_total=total,
                duration_s=duration,
                error=str(exc)[:300],
            )
            chunks_failed.append((chunk_id, str(exc)[:200]))
            console.print(f"  [red]✗ {chunk_id} failed:[/red] {str(exc)[:200]}")

    observability.emit(
        "pipeline_end",
        duration_s=round(time.monotonic() - pipeline_started, 2),
        chunks_ok=len(chunks_ok),
        chunks_failed=len(chunks_failed),
    )

    if chunks_failed:
        console.print(
            f"\n[yellow bold]⚠ {len(chunks_failed)} chunk(s) failed; "
            f"{len(chunks_ok)} succeeded[/yellow bold]"
        )
        for chunk_id, err in chunks_failed:
            console.print(f"  [red]✗[/red] {chunk_id} — {err}")
        raise typer.Exit(code=1)
    console.print(f"\n[green bold]✓ All {total} COMEX chunk(s) complete[/green bold]")


@ingest_app.command("all")
def ingest_all(
    full: bool = typer.Option(
        False,
        "--full",
        help="Force full refetch on delta-aware pipelines (IBGE always fetches its full window).",
    ),
) -> None:
    """Run every registered Bronze pipeline sequentially in INGESTS order."""
    settings = get_settings()
    for spec in INGESTS:
        console.print(f"[bold]→ {spec.label}[/bold]")
        kwargs = {"full": full} if spec.accepts_full else {}
        # Wrap each pipeline in the same observability lifecycle the individual
        # `ingest <source>` commands use, so `ingest all` shows up in
        # `embrapa monitor` and a mid-batch failure leaves a chunk_error in the
        # event log instead of running completely silent.
        with pipeline_run(spec.name, params=kwargs) as (_run_id, log_path):
            console.print(f"[dim]event log:[/dim] {log_path}")
            spec.module.run(settings, **kwargs)
    console.print("[green bold]✓ All Bronze pipelines completed[/green bold]")


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
