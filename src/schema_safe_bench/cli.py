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
from schema_safe_bench.evaluation import (
    build_schema_evidence_report,
    file_sha256,
    load_schema_evidence_report,
    run_evaluator_compatibility,
    write_compatibility_report,
    write_schema_evidence_report,
)
from schema_safe_bench.models import ExecutionLimits
from schema_safe_bench.reporting import compare_paired_runs, load_traces, write_run_comparison
from schema_safe_bench.retrieval import cache_sentence_transformer
from schema_safe_bench.runner import load_hosted_run_config, run_and_write, run_hosted_and_write

app = typer.Typer(no_args_is_help=True, help="Schema-grounded text-to-SQL evaluation.")
dataset_app = typer.Typer(no_args_is_help=True, help="Inspect and prepare benchmark tasks.")
catalog_app = typer.Typer(no_args_is_help=True, help="Extract database schema catalogs.")
run_app = typer.Typer(no_args_is_help=True, help="Run versioned evaluations.")
evaluation_app = typer.Typer(no_args_is_help=True, help="Verify evaluation compatibility.")
results_app = typer.Typer(no_args_is_help=True, help="Compare and inspect benchmark results.")
retrieval_app = typer.Typer(no_args_is_help=True, help="Prepare local retrieval models.")
app.add_typer(dataset_app, name="dataset")
app.add_typer(catalog_app, name="catalog")
app.add_typer(run_app, name="run")
app.add_typer(evaluation_app, name="evaluation")
app.add_typer(results_app, name="results")
app.add_typer(retrieval_app, name="retrieval")


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
    row_limit: Annotated[int, typer.Option(min=1, max=100_000)] = 100_000,
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


@run_app.command("hosted")
def run_hosted(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    replay_only: Annotated[
        bool,
        typer.Option(help="Require recorded responses and make no hosted API calls."),
    ] = False,
    output: Annotated[Path | None, typer.Option(dir_okay=False)] = None,
) -> None:
    """Generate or replay hosted responses and evaluate them through the shared pipeline."""
    traces_path, summary_path = run_hosted_and_write(
        config, replay_only=replay_only, output_path=output
    )
    typer.echo(f"Wrote traces to {traces_path}")
    typer.echo(f"Wrote summary to {summary_path}")


@retrieval_app.command("cache-model")
def cache_retrieval_model(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Download and verify a revision-pinned local dense-retrieval model."""
    run_config = load_hosted_run_config(config)
    if run_config.method_id not in {"B3", "B4"} or not run_config.schema_context:
        raise typer.BadParameter("configuration must define a B3 or B4 local-embedding method")
    embedding = run_config.schema_context.embedding
    if embedding is None:
        raise typer.BadParameter("retrieval configuration must define an embedding model")
    embedder = cache_sentence_transformer(embedding)
    typer.echo(
        f"Cached {embedding.model_id}@{embedding.revision} "
        f"({embedding.embedding_dimension} dimensions, sentence-transformers "
        f"{embedder.library_version})"
    )


@results_app.command("compare")
def compare_results_command(
    baseline: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    treatment: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    baseline_evidence: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, readable=True)
    ] = None,
    treatment_evidence: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, readable=True)
    ] = None,
) -> None:
    """Write a paired comparison for two trace files with identical task IDs."""
    comparison = compare_paired_runs(
        load_traces(baseline),
        load_traces(treatment),
        baseline_evidence=(
            load_schema_evidence_report(baseline_evidence) if baseline_evidence else None
        ),
        treatment_evidence=(
            load_schema_evidence_report(treatment_evidence) if treatment_evidence else None
        ),
    )
    path = write_run_comparison(comparison, output)
    typer.echo(f"Wrote paired comparison to {path}")


@results_app.command("schema-evidence")
def schema_evidence_command(
    trace: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    databases: Annotated[Path, typer.Option(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    """Measure prompt-visible schema evidence after generation has completed."""
    report = build_schema_evidence_report(
        load_traces(trace),
        tasks_path=tasks,
        databases_root=databases,
        source_trace_sha256=file_sha256(trace),
    )
    path = write_schema_evidence_report(report, output)
    typer.echo(f"Wrote evaluator-only schema evidence to {path}")


@evaluation_app.command("compatibility")
def evaluator_compatibility(
    official_checkout: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    databases: Annotated[Path, typer.Option(exists=True, file_okay=False, readable=True)],
    manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    """Cross-check the official BIRD EX evaluator and smoke manifest."""
    report = run_evaluator_compatibility(
        official_checkout=official_checkout,
        tasks_path=tasks,
        databases_root=databases,
        manifest_path=manifest,
    )
    write_compatibility_report(report, output)
    typer.echo(
        f"Matched {report.edge_case_matches}/{report.edge_case_count} edge cases and "
        f"{report.smoke_task_matches}/{report.smoke_task_count} smoke tasks"
    )
    if report.mismatches:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
