"""Execution-result comparison and official evaluator compatibility."""

from schema_safe_bench.evaluation.compatibility import (
    run_evaluator_compatibility,
    write_compatibility_report,
)
from schema_safe_bench.evaluation.results import compare_results, query_is_order_sensitive
from schema_safe_bench.evaluation.schema_evidence import (
    build_schema_evidence_report,
    evaluate_schema_evidence,
    file_sha256,
    load_schema_evidence_report,
    write_schema_evidence_report,
)

__all__ = [
    "build_schema_evidence_report",
    "compare_results",
    "evaluate_schema_evidence",
    "file_sha256",
    "load_schema_evidence_report",
    "query_is_order_sensitive",
    "run_evaluator_compatibility",
    "write_compatibility_report",
    "write_schema_evidence_report",
]
