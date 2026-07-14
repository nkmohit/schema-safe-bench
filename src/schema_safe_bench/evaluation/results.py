"""Deterministic result equivalence helpers."""

import math
from collections import Counter
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from schema_safe_bench.models import ExecutionResult, ResultComparison


def query_is_order_sensitive(sql: str) -> bool:
    """Treat explicit ordering or limiting as order-sensitive evaluation."""
    try:
        statement = parse_one(sql, read="sqlite")
    except ParseError:
        return False
    return statement.find(exp.Order) is not None or statement.find(exp.Limit) is not None


def _value_key(value: Any) -> tuple[str, str]:
    if value is None:
        return ("null", "")
    if isinstance(value, bytes):
        return ("bytes", value.hex())
    if isinstance(value, float):
        if math.isnan(value):
            return ("number", "nan")
        if math.isinf(value):
            return ("number", "inf" if value > 0 else "-inf")
        return ("number", format(value, ".12g"))
    if isinstance(value, int):
        return ("number", str(value))
    return (type(value).__name__, str(value))


def _row_key(row: list[Any]) -> tuple[tuple[str, str], ...]:
    return tuple(_value_key(value) for value in row)


def compare_results(
    candidate: ExecutionResult,
    reference: ExecutionResult,
    *,
    order_sensitive: bool,
) -> ResultComparison:
    """Compare successful, untruncated result sets with bag semantics by default."""
    if candidate.status != "success":
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive,
            reason=f"candidate status is {candidate.status}",
        )
    if reference.status != "success":
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive,
            reason=f"reference status is {reference.status}",
        )
    if candidate.truncated or reference.truncated:
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive,
            reason="truncated results are not comparable",
        )
    if len(candidate.columns) != len(reference.columns):
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive,
            reason="column counts differ",
        )

    candidate_rows = [_row_key(row) for row in candidate.rows]
    reference_rows = [_row_key(row) for row in reference.rows]
    equivalent = (
        candidate_rows == reference_rows
        if order_sensitive
        else Counter(candidate_rows) == Counter(reference_rows)
    )
    return ResultComparison(
        equivalent=equivalent,
        order_sensitive=order_sensitive,
        reason="results match" if equivalent else "result rows differ",
    )
