from pathlib import Path

import pytest

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.validation import SqlValidator


@pytest.fixture
def validator(sample_database: Path) -> SqlValidator:
    return SqlValidator(extract_catalog(sample_database))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM customers",
        (
            "SELECT c.name, SUM(o.amount) AS total FROM customers AS c "
            "JOIN orders AS o ON c.customer_id = o.customer_id GROUP BY c.name"
        ),
        (
            "WITH totals AS (SELECT customer_id, SUM(amount) AS total FROM orders "
            "GROUP BY customer_id) SELECT customer_id, total FROM totals"
        ),
        "SELECT 1",
    ],
)
def test_validator_accepts_read_queries(validator: SqlValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert result.accepted, result.issues


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("DELETE FROM orders", "non_read_query"),
        ("DROP TABLE orders", "non_read_query"),
        ("SELECT 1; SELECT 2", "statement_count"),
        ("SELECT * FROM missing", "unknown_table"),
        ("SELECT missing FROM orders", "unknown_column"),
        ("SELECT x.amount FROM orders", "unknown_qualifier"),
        ("SELECT load_extension('x')", "blocked_function"),
        ("", "empty_query"),
    ],
)
def test_validator_rejects_policy_and_identifier_failures(
    validator: SqlValidator, sql: str, code: str
) -> None:
    result = validator.validate(sql)
    assert result.status == "invalid"
    assert code in {issue.code for issue in result.issues}


def test_validator_records_abstention(validator: SqlValidator) -> None:
    result = validator.validate(" ABSTAIN ")
    assert result.status == "abstain"
    assert not result.accepted


def test_validator_enforces_length(validator: SqlValidator) -> None:
    result = SqlValidator(validator.catalog, max_query_length=5).validate("SELECT 1")
    assert result.issues[0].code == "query_too_long"
