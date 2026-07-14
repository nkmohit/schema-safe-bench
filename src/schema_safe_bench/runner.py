"""Config-driven offline smoke evaluation."""

import json
from pathlib import Path

import yaml

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import find_database, load_bird_tasks
from schema_safe_bench.evaluation import compare_results, query_is_order_sensitive
from schema_safe_bench.execution import execute_read_only
from schema_safe_bench.models import (
    AuditTrace,
    Prediction,
    RunSummary,
    SmokeRunConfig,
    TaskManifest,
)
from schema_safe_bench.reporting import write_run_artifacts
from schema_safe_bench.validation import SqlValidator


def load_run_config(path: Path) -> SmokeRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Run configuration must be a mapping")
    return SmokeRunConfig.model_validate(payload)


def _load_predictions(path: Path) -> dict[str, Prediction]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = [
            {"task_id": task_id, "sql": value}
            if isinstance(value, str)
            else {"task_id": task_id, **value}
            for task_id, value in payload.items()
        ]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Predictions must be a task mapping or list")
    predictions = [Prediction.model_validate(record) for record in records]
    if len({prediction.task_id for prediction in predictions}) != len(predictions):
        raise ValueError("Prediction task IDs must be unique")
    return {prediction.task_id: prediction for prediction in predictions}


def run_offline_smoke(config: SmokeRunConfig) -> tuple[list[AuditTrace], RunSummary]:
    tasks = {task.task_id: task for task in load_bird_tasks(config.tasks_path)}
    manifest = TaskManifest.model_validate_json(config.manifest_path.read_text(encoding="utf-8"))
    predictions = _load_predictions(config.predictions_path)
    traces: list[AuditTrace] = []
    for task_id in manifest.task_ids:
        if task_id not in tasks:
            raise KeyError(f"Manifest task {task_id!r} is absent from the dataset")
        if task_id not in predictions:
            raise KeyError(f"Prediction for task {task_id!r} is missing")
        task = tasks[task_id]
        prediction = predictions[task_id]
        database = find_database(config.databases_root, task.db_id)
        validator = SqlValidator(extract_catalog(database, db_id=task.db_id))
        validation = validator.validate(prediction.sql)
        execution = execute_read_only(database, validation, limits=config.execution)
        reference_validation = validator.validate(task.reference_sql)
        if not reference_validation.accepted:
            raise ValueError(f"Reference SQL failed validation for task {task_id!r}")
        reference_execution = execute_read_only(
            database, reference_validation, limits=config.execution
        )
        comparison = None
        failure_label = None
        if validation.status == "abstain":
            failure_label = "safe_abstention"
        elif validation.status == "invalid":
            failure_label = "validator_rejection"
        elif execution.status != "success":
            failure_label = "execution_failure"
        else:
            comparison = compare_results(
                execution,
                reference_execution,
                order_sensitive=query_is_order_sensitive(task.reference_sql),
            )
            if not comparison.equivalent:
                failure_label = "semantic_mismatch"
        traces.append(
            AuditTrace(
                run_id=config.run_id,
                task_id=task_id,
                db_id=task.db_id,
                method_id=config.method_id,
                question=task.question,
                candidate_sql=prediction.sql,
                raw_output=prediction.raw_output or prediction.sql,
                validation=validation,
                execution=execution,
                reference_execution=reference_execution,
                comparison=comparison,
                failure_label=failure_label,
            )
        )

    summary = RunSummary(
        run_id=config.run_id,
        method_id=config.method_id,
        tasks=len(traces),
        correct=sum(bool(trace.comparison and trace.comparison.equivalent) for trace in traces),
        abstained=sum(trace.validation.status == "abstain" for trace in traces),
        invalid=sum(trace.validation.status == "invalid" for trace in traces),
        execution_errors=sum(
            trace.execution.status in {"error", "interrupted"} for trace in traces
        ),
    )
    return traces, summary


def run_and_write(config_path: Path) -> tuple[Path, Path]:
    config = load_run_config(config_path)
    traces, summary = run_offline_smoke(config)
    return write_run_artifacts(traces, summary, config.output_path)
