"""Paired comparison of auditable benchmark traces."""

from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    ComparedRunMetrics,
    PairedRunComparison,
    PairedTaskOutcome,
    SchemaEvidenceReport,
)


def load_traces(path: Path) -> list[AuditTrace]:
    traces = [
        AuditTrace.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not traces:
        raise ValueError("trace file must contain at least one task")
    if len({trace.task_id for trace in traces}) != len(traces):
        raise ValueError("trace task IDs must be unique")
    return traces


def _outcome(trace: AuditTrace) -> str:
    if trace.comparison and trace.comparison.equivalent:
        return "correct"
    return trace.failure_label or "unclassified_failure"


def _single_value(values: set[str | None], label: str) -> str:
    if len(values) != 1 or None in values:
        raise ValueError(f"traces must have exactly one non-null {label}")
    return next(value for value in values if value is not None)


def _metrics(
    traces: list[AuditTrace], evidence: SchemaEvidenceReport | None = None
) -> ComparedRunMetrics:
    outcomes = Counter(_outcome(trace) for trace in traces)
    correct = outcomes.pop("correct", 0)
    generations = [trace.generation for trace in traces if trace.generation]
    run_id = _single_value({trace.run_id for trace in traces}, "run ID")
    method_id = _single_value({trace.method_id for trace in traces}, "method ID")
    configuration_sha256 = _single_value(
        {trace.configuration_sha256 for trace in traces}, "configuration digest"
    )
    if evidence and (
        evidence.run_id != run_id
        or evidence.method_id != method_id
        or evidence.configuration_sha256 != configuration_sha256
        or evidence.aggregate.tasks != len(traces)
    ):
        raise ValueError("schema evidence report does not match its trace run")
    return ComparedRunMetrics(
        run_id=run_id,
        method_id=method_id,
        configuration_sha256=configuration_sha256,
        software_revisions=sorted(
            revision
            for revision in {trace.software_revision for trace in traces}
            if revision is not None
        ),
        tasks=len(traces),
        correct=correct,
        accuracy=correct / len(traces),
        abstained=sum(trace.validation.status == "abstain" for trace in traces),
        invalid=sum(trace.validation.status == "invalid" for trace in traces),
        execution_errors=sum(
            trace.execution.status in {"error", "interrupted"} for trace in traces
        ),
        failure_categories=dict(sorted(outcomes.items())),
        schema_chars=sum(
            len(trace.schema_pack.serialized) for trace in traces if trace.schema_pack
        ),
        input_tokens=sum(response.input_tokens or 0 for response in generations),
        output_tokens=sum(response.output_tokens or 0 for response in generations),
        estimated_cost_usd=round(
            sum(response.estimated_cost_usd or 0.0 for response in generations), 8
        ),
        schema_evidence=evidence.aggregate if evidence else None,
    )


def compare_paired_runs(
    baseline_traces: list[AuditTrace],
    treatment_traces: list[AuditTrace],
    *,
    baseline_evidence: SchemaEvidenceReport | None = None,
    treatment_evidence: SchemaEvidenceReport | None = None,
) -> PairedRunComparison:
    baseline = {trace.task_id: trace for trace in baseline_traces}
    treatment = {trace.task_id: trace for trace in treatment_traces}
    if set(baseline) != set(treatment):
        raise ValueError("paired runs must contain identical task IDs")

    paired = []
    for task_id in sorted(baseline):
        baseline_trace = baseline[task_id]
        treatment_trace = treatment[task_id]
        baseline_outcome = _outcome(baseline_trace)
        treatment_outcome = _outcome(treatment_trace)
        if baseline_outcome != "correct" and treatment_outcome == "correct":
            change = "improved"
        elif baseline_outcome == "correct" and treatment_outcome != "correct":
            change = "regressed"
        else:
            change = "unchanged"
        paired.append(
            PairedTaskOutcome(
                task_id=task_id,
                baseline_outcome=baseline_outcome,
                treatment_outcome=treatment_outcome,
                correctness_change=change,
                baseline_schema_chars=(
                    len(baseline_trace.schema_pack.serialized) if baseline_trace.schema_pack else 0
                ),
                treatment_schema_chars=(
                    len(treatment_trace.schema_pack.serialized)
                    if treatment_trace.schema_pack
                    else 0
                ),
            )
        )

    if (baseline_evidence is None) != (treatment_evidence is None):
        raise ValueError("paired comparisons require both schema evidence reports or neither")
    baseline_metrics = _metrics(baseline_traces, baseline_evidence)
    treatment_metrics = _metrics(treatment_traces, treatment_evidence)
    improved = [item.task_id for item in paired if item.correctness_change == "improved"]
    regressed = [item.task_id for item in paired if item.correctness_change == "regressed"]
    unchanged = [item.task_id for item in paired if item.correctness_change == "unchanged"]
    return PairedRunComparison(
        baseline=baseline_metrics,
        treatment=treatment_metrics,
        deltas={
            "correct": treatment_metrics.correct - baseline_metrics.correct,
            "accuracy": round(treatment_metrics.accuracy - baseline_metrics.accuracy, 8),
            "abstained": treatment_metrics.abstained - baseline_metrics.abstained,
            "invalid": treatment_metrics.invalid - baseline_metrics.invalid,
            "execution_errors": (
                treatment_metrics.execution_errors - baseline_metrics.execution_errors
            ),
            "schema_chars": treatment_metrics.schema_chars - baseline_metrics.schema_chars,
            "input_tokens": treatment_metrics.input_tokens - baseline_metrics.input_tokens,
            "output_tokens": treatment_metrics.output_tokens - baseline_metrics.output_tokens,
            "estimated_cost_usd": round(
                treatment_metrics.estimated_cost_usd - baseline_metrics.estimated_cost_usd, 8
            ),
        },
        context_truncated_tasks=sum(
            item.treatment_schema_chars < item.baseline_schema_chars for item in paired
        ),
        improved_task_ids=improved,
        regressed_task_ids=regressed,
        unchanged_task_ids=unchanged,
        paired_outcomes=paired,
    )


def write_run_comparison(comparison: PairedRunComparison, path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"Comparison output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        comparison.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
    return path
