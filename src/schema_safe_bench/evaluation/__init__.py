"""Execution-result comparison and official evaluator compatibility."""

from schema_safe_bench.evaluation.compatibility import (
    run_evaluator_compatibility,
    write_compatibility_report,
)
from schema_safe_bench.evaluation.results import compare_results, query_is_order_sensitive

__all__ = [
    "compare_results",
    "query_is_order_sensitive",
    "run_evaluator_compatibility",
    "write_compatibility_report",
]
