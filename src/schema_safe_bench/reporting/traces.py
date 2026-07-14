"""Non-overwriting JSONL result persistence."""

from pathlib import Path

from schema_safe_bench.models import AuditTrace, RunSummary


def write_run_artifacts(
    traces: list[AuditTrace], summary: RunSummary, output_path: Path
) -> tuple[Path, Path]:
    """Create trace and summary files exclusively so prior runs remain immutable."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output_path.with_suffix(".summary.json")
    if output_path.exists() or summary_path.exists():
        raise FileExistsError(f"Run output already exists: {output_path} or {summary_path}")
    with output_path.open("x", encoding="utf-8") as stream:
        for trace in traces:
            stream.write(trace.model_dump_json() + "\n")
    summary_path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path, summary_path
