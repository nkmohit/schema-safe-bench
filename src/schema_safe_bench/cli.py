"""Command-line entry point."""

import json
from pathlib import Path
from typing import Annotated

import typer

from schema_safe_bench.catalog import extract_catalog, write_catalog
from schema_safe_bench.datasets import build_manifest, load_bird_tasks, write_manifest

app = typer.Typer(no_args_is_help=True, help="Schema-grounded text-to-SQL evaluation.")
dataset_app = typer.Typer(no_args_is_help=True, help="Inspect and prepare benchmark tasks.")
catalog_app = typer.Typer(no_args_is_help=True, help="Extract database schema catalogs.")
app.add_typer(dataset_app, name="dataset")
app.add_typer(catalog_app, name="catalog")


@app.callback()
def main() -> None:
    """Run SchemaSafeBench commands."""


@app.command()
def doctor() -> None:
    """Check that the package is installed."""
    typer.echo("SchemaSafeBench is installed.")


@dataset_app.command("inspect")
def inspect_dataset(
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    select_only: Annotated[bool, typer.Option(help="Keep only one-statement read queries.")] = True,
) -> None:
    """Validate and summarize a BIRD task file."""
    normalized = load_bird_tasks(tasks, select_only=select_only)
    summary = {
        "tasks": len(normalized),
        "databases": len({task.db_id for task in normalized}),
        "select_only": select_only,
    }
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@dataset_app.command("manifest")
def create_manifest(
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    revision: Annotated[str, typer.Option(help="Recorded upstream dataset revision.")],
    count: Annotated[int, typer.Option(min=1)] = 20,
    seed: Annotated[int, typer.Option()] = 2026,
) -> None:
    """Create a deterministic SELECT-only task manifest."""
    normalized = load_bird_tasks(tasks, select_only=True)
    manifest = build_manifest(normalized, count=count, seed=seed, dataset_revision=revision)
    write_manifest(manifest, output)
    typer.echo(f"Wrote {len(manifest.task_ids)} task IDs to {output}")


@catalog_app.command("build")
def build_catalog_command(
    database: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    db_id: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Extract a machine-readable SQLite schema catalog."""
    catalog = extract_catalog(database, db_id=db_id)
    write_catalog(catalog, output)
    typer.echo(f"Wrote {len(catalog.tables)} tables to {output}")


if __name__ == "__main__":
    app()
