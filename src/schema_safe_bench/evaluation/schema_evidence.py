"""Evaluator-only measurement of reference-SQL schema evidence."""

import hashlib
from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import find_database, load_bird_tasks
from schema_safe_bench.models import (
    AuditTrace,
    SchemaEvidenceAggregate,
    SchemaEvidenceMetrics,
    SchemaEvidenceReport,
    SchemaEvidenceTask,
    SchemaPack,
    ValidationResult,
)
from schema_safe_bench.validation import SqlValidator


def evaluate_schema_evidence(
    reference_validation: ValidationResult, schema_pack: SchemaPack
) -> SchemaEvidenceMetrics:
    """Compare prompt-visible identifiers with validated reference identifiers."""
    if not reference_validation.accepted:
        raise ValueError("reference SQL must be valid before measuring schema evidence")
    required_tables = set(reference_validation.referenced_tables)
    required_columns = set(reference_validation.referenced_columns)
    selected_tables = {table.name for table in schema_pack.tables}
    selected_columns = {
        f"{table.name}.{column.name}" for table in schema_pack.tables for column in table.columns
    }
    table_tp = len(required_tables & selected_tables)
    column_tp = len(required_columns & selected_columns)
    required_combined = len(required_tables) + len(required_columns)
    selected_combined = len(selected_tables) + len(selected_columns)
    combined_tp = table_tp + column_tp

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    def precision(true_positives: int, selected: int, required: int) -> float:
        return true_positives / selected if selected else float(required == 0)

    return SchemaEvidenceMetrics(
        required_tables=sorted(required_tables, key=str.casefold),
        required_columns=sorted(required_columns, key=str.casefold),
        selected_tables=sorted(selected_tables, key=str.casefold),
        selected_columns=sorted(selected_columns, key=str.casefold),
        missing_tables=sorted(required_tables - selected_tables, key=str.casefold),
        missing_columns=sorted(required_columns - selected_columns, key=str.casefold),
        table_true_positives=table_tp,
        column_true_positives=column_tp,
        table_recall=ratio(table_tp, len(required_tables)),
        table_precision=precision(table_tp, len(selected_tables), len(required_tables)),
        column_recall=ratio(column_tp, len(required_columns)),
        column_precision=precision(column_tp, len(selected_columns), len(required_columns)),
        combined_recall=ratio(combined_tp, required_combined),
        combined_precision=precision(combined_tp, selected_combined, required_combined),
    )


def _aggregate(metrics: list[SchemaEvidenceMetrics]) -> SchemaEvidenceAggregate:
    if not metrics:
        raise ValueError("schema evidence report requires at least one task")

    def macro(field: str) -> float:
        return sum(float(getattr(item, field)) for item in metrics) / len(metrics)

    table_tp = sum(item.table_true_positives for item in metrics)
    column_tp = sum(item.column_true_positives for item in metrics)
    required_tables = sum(len(item.required_tables) for item in metrics)
    selected_tables = sum(len(item.selected_tables) for item in metrics)
    required_columns = sum(len(item.required_columns) for item in metrics)
    selected_columns = sum(len(item.selected_columns) for item in metrics)

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    def precision(true_positives: int, selected: int, required: int) -> float:
        return true_positives / selected if selected else float(required == 0)

    return SchemaEvidenceAggregate(
        tasks=len(metrics),
        tasks_with_full_table_recall=sum(item.table_recall == 1.0 for item in metrics),
        tasks_with_full_column_recall=sum(item.column_recall == 1.0 for item in metrics),
        retrieval_misses=sum(bool(item.missing_tables or item.missing_columns) for item in metrics),
        macro_table_recall=macro("table_recall"),
        macro_table_precision=macro("table_precision"),
        macro_column_recall=macro("column_recall"),
        macro_column_precision=macro("column_precision"),
        macro_combined_recall=macro("combined_recall"),
        macro_combined_precision=macro("combined_precision"),
        micro_table_recall=ratio(table_tp, required_tables),
        micro_table_precision=precision(table_tp, selected_tables, required_tables),
        micro_column_recall=ratio(column_tp, required_columns),
        micro_column_precision=precision(column_tp, selected_columns, required_columns),
    )


def build_schema_evidence_report(
    traces: list[AuditTrace],
    *,
    tasks_path: Path,
    databases_root: Path,
    source_trace_sha256: str,
) -> SchemaEvidenceReport:
    """Build a report after generation using public reference SQL only in evaluation."""
    if not traces:
        raise ValueError("trace file must contain at least one task")
    tasks = {task.task_id: task for task in load_bird_tasks(tasks_path)}
    report_tasks = []
    for trace in traces:
        task = tasks.get(trace.task_id)
        if task is None or task.db_id != trace.db_id or task.question != trace.question:
            raise ValueError(f"trace metadata does not match public task {trace.task_id!r}")
        if trace.schema_pack is None:
            raise ValueError(f"trace {trace.task_id!r} has no prompt-visible schema pack")
        database = find_database(databases_root, trace.db_id)
        catalog = extract_catalog(database, db_id=trace.db_id)
        reference = SqlValidator(catalog).validate(task.reference_sql)
        evidence = evaluate_schema_evidence(reference, trace.schema_pack)
        report_tasks.append(
            SchemaEvidenceTask(task_id=trace.task_id, db_id=trace.db_id, evidence=evidence)
        )
    configuration = {trace.configuration_sha256 for trace in traces}
    run_ids = {trace.run_id for trace in traces}
    method_ids = {trace.method_id for trace in traces}
    if (
        len(configuration) != 1
        or None in configuration
        or len(run_ids) != 1
        or len(method_ids) != 1
    ):
        raise ValueError("traces must describe one run, method, and non-null configuration")
    metrics = [item.evidence for item in report_tasks]
    return SchemaEvidenceReport(
        source_trace_sha256=source_trace_sha256,
        run_id=next(iter(run_ids)),
        method_id=next(iter(method_ids)),
        configuration_sha256=next(value for value in configuration if value is not None),
        aggregate=_aggregate(metrics),
        tasks=report_tasks,
    )


def load_schema_evidence_report(path: Path) -> SchemaEvidenceReport:
    return SchemaEvidenceReport.model_validate_json(path.read_text(encoding="utf-8"))


def write_schema_evidence_report(report: SchemaEvidenceReport, path: Path) -> Path:
    if path.exists():
        raise FileExistsError(f"Schema evidence output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
