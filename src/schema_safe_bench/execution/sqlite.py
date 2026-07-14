"""Defense-in-depth SQLite execution for validated queries."""

import sqlite3
from pathlib import Path
from time import perf_counter

from schema_safe_bench.models import ExecutionLimits, ExecutionResult, ValidationResult

_DENIED_ACTION_NAMES = (
    "SQLITE_ATTACH",
    "SQLITE_CREATE_INDEX",
    "SQLITE_CREATE_TABLE",
    "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER",
    "SQLITE_CREATE_TEMP_VIEW",
    "SQLITE_CREATE_TRIGGER",
    "SQLITE_CREATE_VIEW",
    "SQLITE_DELETE",
    "SQLITE_DETACH",
    "SQLITE_DROP_INDEX",
    "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX",
    "SQLITE_DROP_TEMP_TABLE",
    "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER",
    "SQLITE_DROP_VIEW",
    "SQLITE_INSERT",
    "SQLITE_PRAGMA",
    "SQLITE_REINDEX",
    "SQLITE_TRANSACTION",
    "SQLITE_UPDATE",
)
_DENIED_ACTIONS = {
    getattr(sqlite3, name) for name in _DENIED_ACTION_NAMES if hasattr(sqlite3, name)
}
_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile"}


def execute_read_only(
    database: Path,
    validation: ValidationResult,
    *,
    limits: ExecutionLimits | None = None,
) -> ExecutionResult:
    """Execute only a validator-accepted query against an existing read-only database."""
    if not validation.accepted or validation.normalized_sql is None:
        return ExecutionResult(
            status="rejected",
            error_type="validation_required",
            error_message="Execution requires a valid SQL validation result",
        )
    if not database.is_file():
        return ExecutionResult(
            status="error", error_type="database_not_found", error_message=str(database)
        )

    active_limits = limits or ExecutionLimits()
    callbacks_allowed = max(1, active_limits.vm_step_budget // active_limits.progress_interval)
    callbacks = 0

    def progress() -> int:
        nonlocal callbacks
        callbacks += 1
        return int(callbacks > callbacks_allowed)

    def authorize(
        action: int,
        arg1: str | None,
        arg2: str | None,
        database_name: str | None,
        trigger: str | None,
    ) -> int:
        del database_name, trigger
        if action in _DENIED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if (
            action == sqlite3.SQLITE_FUNCTION
            and (arg2 or arg1 or "").casefold() in _DENIED_FUNCTIONS
        ):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    started = perf_counter()
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"file:{database.resolve().as_posix()}?mode=ro", uri=True, check_same_thread=False
        )
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(authorize)
        connection.set_progress_handler(progress, active_limits.progress_interval)
        cursor = connection.execute(validation.normalized_sql)
        rows = cursor.fetchmany(active_limits.row_limit + 1)
        truncated = len(rows) > active_limits.row_limit
        rows = rows[: active_limits.row_limit]
        return ExecutionResult(
            status="success",
            columns=[description[0] for description in cursor.description or ()],
            rows=[list(row) for row in rows],
            truncated=truncated,
            elapsed_ms=(perf_counter() - started) * 1000,
        )
    except sqlite3.OperationalError as exc:
        message = str(exc)
        interrupted = "interrupted" in message.casefold()
        return ExecutionResult(
            status="interrupted" if interrupted else "error",
            elapsed_ms=(perf_counter() - started) * 1000,
            error_type="query_budget_exceeded" if interrupted else "sqlite_operational_error",
            error_message=message,
        )
    except sqlite3.DatabaseError as exc:
        return ExecutionResult(
            status="error",
            elapsed_ms=(perf_counter() - started) * 1000,
            error_type="sqlite_database_error",
            error_message=str(exc),
        )
    finally:
        if connection is not None:
            connection.close()
