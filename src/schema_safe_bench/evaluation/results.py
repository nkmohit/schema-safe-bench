"""Deterministic result equivalence helpers."""

from collections import Counter
from typing import Literal

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


def compare_results(
    candidate: ExecutionResult,
    reference: ExecutionResult,
    *,
    policy: Literal["bird-execution-v1", "strict-v1"] = "bird-execution-v1",
    order_sensitive: bool = False,
) -> ResultComparison:
    """Compare results under the official BIRD EX or stricter diagnostic policy."""
    if candidate.status != "success":
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive if policy == "strict-v1" else False,
            reason=f"candidate status is {candidate.status}",
            policy=policy,
        )
    if reference.status != "success":
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive if policy == "strict-v1" else False,
            reason=f"reference status is {reference.status}",
            policy=policy,
        )
    if candidate.truncated or reference.truncated:
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive if policy == "strict-v1" else False,
            reason="truncated results are not comparable",
            policy=policy,
        )

    if policy == "bird-execution-v1":
        equivalent = {tuple(row) for row in candidate.rows} == {
            tuple(row) for row in reference.rows
        }
        return ResultComparison(
            equivalent=equivalent,
            order_sensitive=False,
            reason="official BIRD result sets match" if equivalent else "result sets differ",
            policy=policy,
        )

    if len(candidate.columns) != len(reference.columns):
        return ResultComparison(
            equivalent=False,
            order_sensitive=order_sensitive,
            reason="column counts differ",
            policy=policy,
        )

    candidate_rows = [tuple(row) for row in candidate.rows]
    reference_rows = [tuple(row) for row in reference.rows]
    equivalent = (
        candidate_rows == reference_rows
        if order_sensitive
        else Counter(candidate_rows) == Counter(reference_rows)
    )
    return ResultComparison(
        equivalent=equivalent,
        order_sensitive=order_sensitive,
        reason="results match" if equivalent else "result rows differ",
        policy=policy,
    )
