"""Verify prepared public assets without persisting database result rows."""

from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets.bird import find_database, load_bird_tasks
from schema_safe_bench.execution import execute_read_only
from schema_safe_bench.models import (
    AssetTaskCheck,
    AssetVerificationReport,
    ExecutionLimits,
    TaskManifest,
)
from schema_safe_bench.validation import SqlValidator


def verify_bird_assets(
    *,
    tasks_path: Path,
    databases_root: Path,
    manifest_path: Path,
    limits: ExecutionLimits | None = None,
) -> AssetVerificationReport:
    """Catalog and execute each manifest reference query through project guardrails."""
    tasks = {task.task_id: task for task in load_bird_tasks(tasks_path, select_only=True)}
    manifest = TaskManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    active_limits = limits or ExecutionLimits(vm_step_budget=10_000_000)
    validators: dict[str, SqlValidator] = {}
    database_paths: dict[str, Path] = {}
    checks: list[AssetTaskCheck] = []

    for task_id in manifest.task_ids:
        try:
            task = tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Manifest task {task_id!r} is absent from the task file") from exc
        if task.db_id not in validators:
            database = find_database(databases_root, task.db_id)
            database_paths[task.db_id] = database
            validators[task.db_id] = SqlValidator(extract_catalog(database, db_id=task.db_id))
        validator = validators[task.db_id]
        validation = validator.validate(task.reference_sql)
        execution = execute_read_only(database_paths[task.db_id], validation, limits=active_limits)
        checks.append(
            AssetTaskCheck(
                task_id=task.task_id,
                db_id=task.db_id,
                catalog_tables=len(validator.catalog.tables),
                validation_status=validation.status,
                execution_status=execution.status,
                truncated=execution.truncated,
                issue_codes=[issue.code for issue in validation.issues],
            )
        )

    passed = sum(check.passed for check in checks)
    return AssetVerificationReport(
        dataset=manifest.dataset,
        dataset_revision=manifest.dataset_revision,
        manifest_seed=manifest.seed,
        task_count=len(checks),
        database_count=len(validators),
        passed_tasks=passed,
        failed_tasks=len(checks) - passed,
        checks=checks,
    )


def write_asset_verification(report: AssetVerificationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
