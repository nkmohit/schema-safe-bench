"""BIRD Mini-Dev task normalization and asset discovery."""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from schema_safe_bench.models import BenchmarkTask, TaskManifest

_SQL_FIELDS = ("SQL", "sql", "query", "gold_sql")
_TASK_ID_FIELDS = ("question_id", "task_id", "id")


def _read_records(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid dataset JSON: {path}") from exc

    if isinstance(payload, dict):
        for key in ("data", "examples", "tasks"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("Dataset JSON must be a list of task objects")
    return payload


def _first(record: dict[str, Any], fields: Iterable[str]) -> Any:
    for field in fields:
        value = record.get(field)
        if value is not None:
            return value
    return None


def is_select_only(sql: str) -> bool:
    """Return whether reference SQL is exactly one read-only query."""
    try:
        statements = [statement for statement in parse(sql, read="sqlite") if statement]
    except ParseError:
        return False
    return len(statements) == 1 and isinstance(statements[0], exp.Query)


def load_bird_tasks(path: Path, *, select_only: bool = True) -> list[BenchmarkTask]:
    """Normalize common BIRD JSON fields without changing reference SQL."""
    records = _read_records(path)
    tasks: list[BenchmarkTask] = []
    for index, record in enumerate(records):
        db_id = str(record.get("db_id", "")).strip()
        question = str(record.get("question", "")).strip()
        reference_sql = str(_first(record, _SQL_FIELDS) or "").strip()
        raw_id = _first(record, _TASK_ID_FIELDS)
        task_id = str(raw_id if raw_id is not None else f"{db_id}:{index}")
        if select_only and not is_select_only(reference_sql):
            continue
        known_fields = {
            "db_id",
            "question",
            "evidence",
            "difficulty",
            *_SQL_FIELDS,
            *_TASK_ID_FIELDS,
        }
        tasks.append(
            BenchmarkTask(
                task_id=task_id,
                db_id=db_id,
                question=question,
                reference_sql=reference_sql,
                evidence=record.get("evidence"),
                difficulty=record.get("difficulty"),
                metadata={key: value for key, value in record.items() if key not in known_fields},
            )
        )
    if not tasks:
        raise ValueError("No matching benchmark tasks were loaded")
    if len({task.task_id for task in tasks}) != len(tasks):
        raise ValueError("Task IDs must be unique after normalization")
    return tasks


def build_manifest(
    tasks: list[BenchmarkTask],
    *,
    count: int,
    seed: int,
    dataset_revision: str,
) -> TaskManifest:
    """Select tasks by stable hash so input ordering cannot change the sample."""
    if count < 1:
        raise ValueError("count must be positive")
    if count > len(tasks):
        raise ValueError(f"requested {count} tasks from a set of {len(tasks)}")

    def rank(task: BenchmarkTask) -> tuple[str, str]:
        digest = hashlib.sha256(f"{seed}:{task.task_id}".encode()).hexdigest()
        return digest, task.task_id

    selected = sorted(tasks, key=rank)[:count]
    return TaskManifest(
        dataset="bird-minidev-select",
        dataset_revision=dataset_revision,
        selection="sha256(seed:task_id)",
        seed=seed,
        task_ids=[task.task_id for task in selected],
    )


def write_manifest(manifest: TaskManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def find_database(databases_root: Path, db_id: str) -> Path:
    """Find a database inside the configured root without allowing traversal."""
    root = databases_root.resolve(strict=True)
    candidates = (
        root / db_id / f"{db_id}.sqlite",
        root / db_id / f"{db_id}.sqlite3",
        root / db_id / f"{db_id}.db",
        root / f"{db_id}.sqlite",
        root / f"{db_id}.sqlite3",
        root / f"{db_id}.db",
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root) and resolved.is_file():
            return resolved
    raise FileNotFoundError(f"No SQLite database found for db_id={db_id!r} under {root}")
