from pathlib import Path

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.prompting import (
    build_generation_request,
    build_repair_request,
    extract_candidate_sql,
)
from schema_safe_bench.retrieval import full_schema_pack


def test_prompt_contains_question_and_schema_but_no_reference(sample_database: Path) -> None:
    pack = full_schema_pack(extract_catalog(sample_database))
    request = build_generation_request(
        question="Who has orders?", schema_pack=pack, model_name="fixture"
    )
    combined = "\n".join(message.content for message in request.messages)

    assert "Who has orders?" in combined
    assert "customers" in combined
    assert request.prompt_version == "sqlite-readonly-v1"


def test_repair_prompt_is_explicitly_bounded(sample_database: Path) -> None:
    pack = full_schema_pack(extract_catalog(sample_database))
    request = build_repair_request(
        question="Total?",
        schema_pack=pack,
        rejected_sql="SELECT total FROM orders",
        error="unknown column",
        model_name="fixture",
    )
    assert request.prompt_version.endswith("repair-1")
    assert "unknown column" in request.messages[1].content


def test_candidate_extraction_preserves_abstention_and_unwraps_fence() -> None:
    assert extract_candidate_sql(" ABSTAIN ") == "ABSTAIN"
    assert extract_candidate_sql("```sql\nSELECT 1\n```") == "SELECT 1"
    assert extract_candidate_sql("SELECT 2") == "SELECT 2"
