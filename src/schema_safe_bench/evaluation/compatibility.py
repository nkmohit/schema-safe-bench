"""Cross-check SchemaSafeBench against a checksum-pinned official BIRD evaluator."""

import ast
import hashlib
import sqlite3
import subprocess
from collections.abc import Callable
from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import find_database, load_bird_tasks, load_task_manifest
from schema_safe_bench.evaluation.results import compare_results
from schema_safe_bench.execution import execute_read_only
from schema_safe_bench.models import (
    EvaluatorCompatibilityCase,
    EvaluatorCompatibilityReport,
    EvaluatorSmokeCheck,
    ExecutionLimits,
    ExecutionResult,
)
from schema_safe_bench.validation import SqlValidator

OFFICIAL_REPOSITORY = "https://github.com/bird-bench/mini_dev"
OFFICIAL_REPOSITORY_REVISION = "b3d4bcbbae9a96934ad812551eb400c7a3b23c12"
OFFICIAL_EVALUATOR_REVISION = "f9d2750c9b53639820c9d47f6d7a5e5025c780ab"
EVALUATION_EX_SHA256 = "da1bbcd4530be83692d7c650c814ea9704bb710d0c953eb75d02ccb38233cf89"
EVALUATION_UTILS_SHA256 = "f6943d249caac5aeaef9bce21d43dbf29dcef85a0c965a76df032a9542f308bf"

OfficialCalculateEx = Callable[[list[tuple[object, ...]], list[tuple[object, ...]]], int]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_official_calculate_ex(
    source_path: Path, *, expected_sha256: str = EVALUATION_EX_SHA256
) -> OfficialCalculateEx:
    """Load only the checksum-pinned official ``calculate_ex`` function."""
    actual_sha256 = _sha256(source_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Official evaluator checksum mismatch for {source_path}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "calculate_ex"
    ]
    if len(functions) != 1:
        raise ValueError("Official evaluator must define exactly one calculate_ex function")
    isolated = ast.Module(body=functions, type_ignores=[])
    namespace: dict[str, object] = {}
    exec(compile(isolated, str(source_path), "exec"), {"__builtins__": {"set": set}}, namespace)
    calculate = namespace.get("calculate_ex")
    if not callable(calculate):
        raise ValueError("Could not load official calculate_ex function")
    return calculate  # type: ignore[return-value]


def verify_official_checkout(
    checkout: Path,
    *,
    evaluation_ex_sha256: str = EVALUATION_EX_SHA256,
    evaluation_utils_sha256: str = EVALUATION_UTILS_SHA256,
) -> OfficialCalculateEx:
    evaluation_dir = checkout / "evaluation"
    utils_path = evaluation_dir / "evaluation_utils.py"
    actual_utils_sha256 = _sha256(utils_path)
    if actual_utils_sha256 != evaluation_utils_sha256:
        raise ValueError(
            f"Official evaluator checksum mismatch for {utils_path}: "
            f"expected {evaluation_utils_sha256}, got {actual_utils_sha256}"
        )
    return load_official_calculate_ex(
        evaluation_dir / "evaluation_ex.py", expected_sha256=evaluation_ex_sha256
    )


def _result(
    rows: list[list[object]],
    *,
    columns: list[str] | None = None,
    status: str = "success",
) -> ExecutionResult:
    return ExecutionResult(
        status=status,  # type: ignore[arg-type]
        columns=columns or ["value"],
        rows=rows,
    )


def build_edge_case_cross_check(
    official_calculate_ex: OfficialCalculateEx,
) -> list[EvaluatorCompatibilityCase]:
    """Compare semantics that commonly diverge between SQL evaluators."""
    cases: list[tuple[str, ExecutionResult, ExecutionResult, list[tuple[object, ...]] | None]] = [
        ("row_order", _result([[1], [2]]), _result([[2], [1]]), [(1,), (2,)]),
        ("duplicate_rows", _result([[1], [1]]), _result([[1]]), [(1,), (1,)]),
        ("null_values", _result([[None]]), _result([[None]]), [(None,)]),
        ("integer_float_equality", _result([[1]]), _result([[1.0]]), [(1,)]),
        (
            "numeric_precision",
            _result([[1.0000000000001]]),
            _result([[1.0000000000002]]),
            [(1.0000000000001,)],
        ),
        (
            "empty_results_ignore_columns",
            _result([], columns=["one"]),
            _result([], columns=["one", "two"]),
            [],
        ),
        ("execution_error", _result([], status="error"), _result([]), None),
    ]
    checks: list[EvaluatorCompatibilityCase] = []
    for name, candidate, reference, official_candidate in cases:
        if official_candidate is None:
            official_equivalent = False
        else:
            official_reference = [tuple(row) for row in reference.rows]
            official_equivalent = bool(
                official_calculate_ex(official_candidate, official_reference)
            )
        project_equivalent = compare_results(
            candidate, reference, policy="bird-execution-v1"
        ).equivalent
        checks.append(
            EvaluatorCompatibilityCase(
                name=name,
                official_equivalent=official_equivalent,
                project_equivalent=project_equivalent,
                matched=official_equivalent == project_equivalent,
            )
        )
    return checks


def _official_execute(sql: str, database: Path) -> tuple[bool, list[tuple[object, ...]]]:
    try:
        with sqlite3.connect(
            f"file:{database.resolve().as_posix()}?mode=ro", uri=True
        ) as connection:
            rows = connection.execute(sql).fetchall()
        return True, rows
    except sqlite3.Error:
        return False, []


def run_evaluator_compatibility(
    *,
    official_checkout: Path,
    tasks_path: Path,
    databases_root: Path,
    manifest_path: Path,
    limits: ExecutionLimits | None = None,
    evaluation_ex_sha256: str = EVALUATION_EX_SHA256,
    evaluation_utils_sha256: str = EVALUATION_UTILS_SHA256,
    repository_revision: str = OFFICIAL_REPOSITORY_REVISION,
    evaluator_revision: str = OFFICIAL_EVALUATOR_REVISION,
    verify_git_revision: bool = True,
) -> EvaluatorCompatibilityReport:
    """Cross-check edge cases and smoke-manifest reference execution."""
    if verify_git_revision:
        completed = subprocess.run(
            ["git", "-C", str(official_checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        actual_revision = completed.stdout.strip()
        if actual_revision != repository_revision:
            raise ValueError(
                f"Official repository revision mismatch: expected {repository_revision}, "
                f"got {actual_revision}"
            )
    official_calculate_ex = verify_official_checkout(
        official_checkout,
        evaluation_ex_sha256=evaluation_ex_sha256,
        evaluation_utils_sha256=evaluation_utils_sha256,
    )
    edge_cases = build_edge_case_cross_check(official_calculate_ex)
    tasks = {task.task_id: task for task in load_bird_tasks(tasks_path, select_only=True)}
    manifest = load_task_manifest(manifest_path)
    active_limits = limits or ExecutionLimits(row_limit=100_000, vm_step_budget=10_000_000)
    validators: dict[str, SqlValidator] = {}
    database_paths: dict[str, Path] = {}
    smoke_checks: list[EvaluatorSmokeCheck] = []

    for task_id in manifest.task_ids:
        try:
            task = tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Manifest task {task_id!r} is absent from the task file") from exc
        if task.db_id not in validators:
            database = find_database(databases_root, task.db_id)
            database_paths[task.db_id] = database
            validators[task.db_id] = SqlValidator(extract_catalog(database, db_id=task.db_id))
        database = database_paths[task.db_id]
        validation = validators[task.db_id].validate(task.reference_sql)
        project_candidate = execute_read_only(database, validation, limits=active_limits)
        project_reference = execute_read_only(database, validation, limits=active_limits)
        project_success = (
            project_candidate.status == "success"
            and project_reference.status == "success"
            and not project_candidate.truncated
            and not project_reference.truncated
        )
        project_equivalent = compare_results(
            project_candidate,
            project_reference,
            policy="bird-execution-v1",
        ).equivalent

        official_candidate_success, official_candidate_rows = _official_execute(
            task.reference_sql, database
        )
        official_reference_success, official_reference_rows = _official_execute(
            task.reference_sql, database
        )
        official_success = official_candidate_success and official_reference_success
        official_equivalent = official_success and bool(
            official_calculate_ex(official_candidate_rows, official_reference_rows)
        )
        matched = official_success == project_success and official_equivalent == project_equivalent
        smoke_checks.append(
            EvaluatorSmokeCheck(
                task_id=task.task_id,
                db_id=task.db_id,
                official_execution_success=official_success,
                project_execution_success=project_success,
                official_equivalent=official_equivalent,
                project_equivalent=project_equivalent,
                matched=matched,
                result_rows=len(official_reference_rows) if official_success else None,
            )
        )

    mismatches = [f"edge:{case.name}" for case in edge_cases if not case.matched]
    mismatches.extend(f"task:{check.task_id}" for check in smoke_checks if not check.matched)
    return EvaluatorCompatibilityReport(
        official_repository=OFFICIAL_REPOSITORY,
        official_repository_revision=repository_revision,
        official_evaluator_revision=evaluator_revision,
        evaluation_ex_sha256=evaluation_ex_sha256,
        evaluation_utils_sha256=evaluation_utils_sha256,
        edge_case_count=len(edge_cases),
        edge_case_matches=sum(case.matched for case in edge_cases),
        smoke_task_count=len(smoke_checks),
        smoke_task_matches=sum(check.matched for check in smoke_checks),
        mismatches=mismatches,
        edge_cases=edge_cases,
        smoke_checks=smoke_checks,
    )


def write_compatibility_report(report: EvaluatorCompatibilityReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
