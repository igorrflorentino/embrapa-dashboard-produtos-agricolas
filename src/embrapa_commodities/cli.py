"""Embrapa commodities CLI — single entry point for local/manual orchestration."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from embrapa_commodities import discover
from embrapa_commodities.bcb import currency as bcb_currency
from embrapa_commodities.bcb import inflation as bcb_inflation
from embrapa_commodities.config import get_settings
from embrapa_commodities.ibge import pipeline as ibge_pipeline
from embrapa_commodities.ibge.client import recommended_chunk_years

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

console = Console()
app = typer.Typer(no_args_is_help=True, add_completion=False, help="Embrapa commodities pipeline")

ingest_app = typer.Typer(no_args_is_help=True, help="Bronze-layer ingestion commands")
app.add_typer(ingest_app, name="ingest")

discover_app = typer.Typer(
    no_args_is_help=True,
    help="Auxiliary lookups — inspect IBGE / BCB before committing codes to .env",
)
app.add_typer(discover_app, name="discover")


# ─── ingest ───────────────────────────────────────────────────────────────────
@ingest_app.command("ibge")
def ingest_ibge() -> None:
    """Ingest IBGE PEVS into the configured Bronze table."""
    destination = ibge_pipeline.run(get_settings())
    console.print(f"[green]✓[/green] IBGE bronze loaded → {destination}")


@ingest_app.command("bcb-inflation")
def ingest_bcb_inflation() -> None:
    """Ingest configured BCB SGS inflation series."""
    destination = bcb_inflation.run(get_settings())
    console.print(f"[green]✓[/green] BCB inflation bronze loaded → {destination}")


@ingest_app.command("bcb-currency")
def ingest_bcb_currency() -> None:
    """Ingest configured BCB SGS FX series."""
    destination = bcb_currency.run(get_settings())
    console.print(f"[green]✓[/green] BCB currency bronze loaded → {destination}")


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

    for i, chunk_start in enumerate(chunks, 1):
        chunk_end = min(chunk_start + chunk_years - 1, range_end)
        settings.ibge_start_year = chunk_start
        settings.ibge_end_year = chunk_end
        console.print(
            f"  [dim][{i}/{total}][/dim] [bold]-> {chunk_start}-{chunk_end}[/bold]"
        )
        destination = ibge_pipeline.run(settings)
        console.print(f"  [green]✓[/green] loaded → {destination}")

    console.print(f"\n[green bold]✓ All {total} batches complete[/green bold]")


@ingest_app.command("all")
def ingest_all() -> None:
    """Run all three Bronze pipelines sequentially."""
    settings = get_settings()
    console.print("[bold]→ IBGE PEVS[/bold]")
    ibge_pipeline.run(settings)
    console.print("[bold]→ BCB inflation[/bold]")
    bcb_inflation.run(settings)
    console.print("[bold]→ BCB currency[/bold]")
    bcb_currency.run(settings)
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
        f"\n[dim]Suggested .env value:[/dim] "
        f"IBGE_PRODUCT_CODES={','.join(m.code for m in matches)}"
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
        f"[dim]Suggested .env:[/dim] "
        f"IBGE_START_YEAR={years[0]} IBGE_END_YEAR={years[-1]}"
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


# ─── dbt passthrough ──────────────────────────────────────────────────────────
@app.command("dbt")
def dbt_passthrough(
    args: list[str] = typer.Argument(None, help="Arguments forwarded to dbt"),  # noqa: B008
) -> None:
    """Forward arbitrary args to `dbt` from inside the dbt/ project dir."""
    dbt_dir = Path(__file__).resolve().parents[2] / "dbt"
    cmd = ["dbt", *(args or ["--help"])]
    console.print(f"[dim]$ {' '.join(cmd)} (cwd={dbt_dir})[/dim]")
    result = subprocess.run(cmd, cwd=dbt_dir, check=False)
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
