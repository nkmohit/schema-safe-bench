from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.execution import execute_read_only
from schema_safe_bench.models import ExecutionLimits, ValidationResult
from schema_safe_bench.validation import SqlValidator


def test_execute_valid_query_with_row_cap(sample_database: Path) -> None:
    validator = SqlValidator(extract_catalog(sample_database))
    validation = validator.validate("SELECT order_id FROM orders ORDER BY order_id")

    result = execute_read_only(sample_database, validation, limits=ExecutionLimits(row_limit=2))

    assert result.status == "success"
    assert result.rows == [[10], [11]]
    assert result.truncated
    assert result.columns == ["order_id"]


def test_execution_requires_validation(sample_database: Path) -> None:
    result = execute_read_only(sample_database, ValidationResult(status="invalid"))
    assert result.status == "rejected"
    assert result.error_type == "validation_required"


def test_execution_reports_missing_database(tmp_path: Path) -> None:
    result = execute_read_only(
        tmp_path / "missing.sqlite",
        ValidationResult(status="valid", normalized_sql="SELECT 1"),
    )
    assert result.status == "error"
    assert result.error_type == "database_not_found"


def test_read_only_connection_does_not_mutate_database(sample_database: Path) -> None:
    validator = SqlValidator(extract_catalog(sample_database))
    rejected = validator.validate("UPDATE orders SET amount = 0")

    result = execute_read_only(sample_database, rejected)

    assert result.status == "rejected"
