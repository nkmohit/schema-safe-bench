"""Command-line entry point."""

import json
from pathlib import Path
from typing import Annotated

import typer

from schema_safe_bench.catalog import extract_catalog, write_catalog
from schema_safe_bench.datasets import (
    build_manifest,
    load_bird_tasks,
    verify_bird_assets,
    write_asset_verification,
    write_manifest,
)
from schema_safe_bench.models import ExecutionLimits
from schema_safe_bench.runner import run_and_write

app = typer.Typer(no_args_is_help=True, help="Schema-grounded text-to-SQL evaluation.")
dataset_app = typer.Typer(no_args_is_help=True, help="Inspect and prepare benchmark tasks.")
catalog_app = typer.Typer(no_args_is_help=True, help="Extract database schema catalogs.")
run_app = typer.Typer(no_args_is_help=True, help="Run versioned evaluations.")
app.add_typer(dataset_app, name="dataset")
app.add_typer(catalog_app, name="catalog")
app.add_typer(run_app, name="run")


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


@dataset_app.command("verify")
def verify_dataset(
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    databases: Annotated[Path, typer.Option(exists=True, file_okay=False, readable=True)],
    manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    row_limit: Annotated[int, typer.Option(min=1, max=100_000)] = 1000,
    vm_step_budget: Annotated[int, typer.Option(min=1000)] = 10_000_000,
) -> None:
    """Verify catalogs and reference execution for a committed task manifest."""
    report = verify_bird_assets(
        tasks_path=tasks,
        databases_root=databases,
        manifest_path=manifest,
        limits=ExecutionLimits(row_limit=row_limit, vm_step_budget=vm_step_budget),
    )
    write_asset_verification(report, output)
    typer.echo(
        f"Verified {report.passed_tasks}/{report.task_count} tasks "
        f"across {report.database_count} databases"
    )
    if report.failed_tasks:
        raise typer.Exit(code=1)


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


@run_app.command("smoke")
def run_smoke(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Evaluate saved predictions using a versioned smoke configuration."""
    traces_path, summary_path = run_and_write(config)
    typer.echo(f"Wrote traces to {traces_path}")
    typer.echo(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    app()
