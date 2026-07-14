import pytest

from schema_safe_bench.evaluation import compare_results, query_is_order_sensitive
from schema_safe_bench.models import ExecutionResult


def _result(rows: list[list[object]], *, status: str = "success") -> ExecutionResult:
    return ExecutionResult(status=status, columns=["value"], rows=rows)  # type: ignore[arg-type]


def test_unordered_comparison_uses_bag_semantics() -> None:
    comparison = compare_results(
        _result([[1], [2], [2]]), _result([[2], [1], [2]]), order_sensitive=False
    )
    assert comparison.equivalent


def test_ordered_comparison_preserves_sequence() -> None:
    comparison = compare_results(_result([[1], [2]]), _result([[2], [1]]), order_sensitive=True)
    assert not comparison.equivalent


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT * FROM t ORDER BY x", True),
        ("SELECT * FROM t LIMIT 1", True),
        ("SELECT * FROM t", False),
    ],
)
def test_order_sensitivity_detection(sql: str, expected: bool) -> None:
    assert query_is_order_sensitive(sql) is expected


def test_comparison_rejects_failed_or_truncated_results() -> None:
    failed = compare_results(_result([], status="error"), _result([]), order_sensitive=False)
    truncated = compare_results(
        ExecutionResult(status="success", columns=["x"], rows=[[1]], truncated=True),
        _result([[1]]),
        order_sensitive=False,
    )
    assert failed.reason == "candidate status is error"
    assert truncated.reason == "truncated results are not comparable"
