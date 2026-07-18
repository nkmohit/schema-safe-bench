import hashlib
import json
from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.evaluation import (
    build_schema_evidence_report,
    evaluate_schema_evidence,
)
from schema_safe_bench.models import AuditTrace, ExecutionResult, ValidationResult
from schema_safe_bench.retrieval import BM25Retriever, build_schema_documents, build_schema_pack
from schema_safe_bench.validation import SqlValidator


def test_schema_evidence_measures_prompt_visible_identifiers(sample_database: Path) -> None:
    catalog = extract_catalog(sample_database, db_id="shop")
    reference = SqlValidator(catalog).validate(
        "SELECT customers.name FROM customers "
        "JOIN orders ON customers.customer_id = orders.customer_id"
    )
    hits = BM25Retriever(build_schema_documents(catalog)).retrieve("customer name", top_k=2)
    evidence = evaluate_schema_evidence(reference, build_schema_pack(catalog, hits))

    assert evidence.required_tables == ["customers", "orders"]
    assert evidence.table_recall < 1.0
    assert evidence.missing_tables == ["orders"]


def test_schema_evidence_report_recomputes_from_public_reference(
    sample_database: Path, tmp_path: Path
) -> None:
    database_dir = tmp_path / "databases" / "shop"
    database_dir.mkdir(parents=True)
    database = database_dir / "shop.sqlite"
    database.write_bytes(sample_database.read_bytes())
    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "List customer names",
                    "SQL": "SELECT name FROM customers",
                }
            ]
        ),
        encoding="utf-8",
    )
    catalog = extract_catalog(database, db_id="shop")
    pack = build_schema_pack(
        catalog,
        BM25Retriever(build_schema_documents(catalog)).retrieve("customer names", top_k=2),
    )
    success = ExecutionResult(status="success")
    trace = AuditTrace(
        run_id="r",
        task_id="1",
        db_id="shop",
        method_id="B2",
        question="List customer names",
        candidate_sql="SELECT name FROM customers",
        raw_output="SELECT name FROM customers",
        configuration_sha256="a" * 64,
        schema_pack=pack,
        validation=ValidationResult(status="valid", normalized_sql="SELECT name FROM customers"),
        execution=success,
        reference_execution=success,
    )
    report = build_schema_evidence_report(
        [trace],
        tasks_path=tasks,
        databases_root=tmp_path / "databases",
        source_trace_sha256=hashlib.sha256(b"trace").hexdigest(),
    )

    assert report.aggregate.tasks == 1
    assert report.aggregate.tasks_with_full_table_recall == 1
    assert report.tasks[0].evidence.required_columns == ["customers.name"]
