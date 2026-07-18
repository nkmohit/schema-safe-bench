from pathlib import Path

import pytest

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.retrieval import (
    BM25Retriever,
    DenseRetriever,
    HybridRetriever,
    build_schema_documents,
    build_schema_pack,
    full_schema_pack,
    length_truncated_schema_pack,
)


def _embed(texts: list[str]) -> list[list[float]]:
    return [
        [float("customer" in text.casefold()), float("amount" in text.casefold()), 1.0]
        for text in texts
    ]


def test_bm25_ranking_is_stable(sample_database: Path) -> None:
    catalog = extract_catalog(sample_database)
    retriever = BM25Retriever(build_schema_documents(catalog))
    hits = retriever.retrieve("customer name", top_k=3)

    assert hits[0].table_name == "customers"
    assert [hit.rank for hit in hits] == [1, 2, 3]


def test_dense_and_hybrid_retrieval(sample_database: Path) -> None:
    documents = build_schema_documents(extract_catalog(sample_database))
    lexical = BM25Retriever(documents)
    dense = DenseRetriever(documents, _embed)
    hybrid = HybridRetriever(lexical, dense)

    dense_hits = dense.retrieve("total amount", top_k=2)
    hybrid_hits = hybrid.retrieve("total amount", top_k=2)

    assert any(hit.column_name == "amount" for hit in dense_hits)
    assert len(hybrid_hits) == 2
    assert set(hybrid_hits[0].component_scores) <= {"bm25", "dense"}


def test_schema_pack_includes_join_edges(sample_database: Path) -> None:
    catalog = extract_catalog(sample_database)
    documents = build_schema_documents(catalog)
    hits = BM25Retriever(documents).retrieve("customers order amount", top_k=6)
    pack = build_schema_pack(catalog, hits)

    assert {table.name for table in pack.tables} == {"customers", "orders"}
    assert "orders.customer_id -> customers.customer_id" in pack.foreign_keys
    assert "FK orders.customer_id" in pack.serialized
    visible = {table.name: {column.name for column in table.columns} for table in pack.tables}
    assert "customer_id" in visible["orders"]
    assert "customer_id" in visible["customers"]


def test_bm25_zero_score_ties_use_document_id(sample_database: Path) -> None:
    documents = build_schema_documents(extract_catalog(sample_database))
    hits = BM25Retriever(documents, k1=1.5, b=0.75, epsilon=0.25).retrieve(
        "termabsentfromcatalog", top_k=4
    )

    assert [hit.document_id for hit in hits] == sorted(
        document.document_id for document in documents
    )[:4]
    assert all(hit.score == 0.0 for hit in hits)


def test_full_schema_pack_can_be_truncated(sample_database: Path) -> None:
    pack = full_schema_pack(extract_catalog(sample_database), max_chars=20)
    assert len(pack.serialized) == 20
    assert len(pack.tables) == 2


def test_length_truncated_pack_contains_only_complete_visible_schema(
    sample_database: Path,
) -> None:
    catalog = extract_catalog(sample_database)
    first = length_truncated_schema_pack(catalog, max_chars=80)
    second = length_truncated_schema_pack(catalog, max_chars=80)

    assert first == second
    assert len(first.serialized) <= 80
    assert first.tables
    assert first.serialized.endswith(")")
    assert all(table.name in first.serialized for table in first.tables)
    assert all(
        column.name in first.serialized for table in first.tables for column in table.columns
    )
    assert all(f"FK {foreign_key}" in first.serialized for foreign_key in first.foreign_keys)


def test_length_truncated_pack_preserves_schema_that_fits(sample_database: Path) -> None:
    catalog = extract_catalog(sample_database)
    assert length_truncated_schema_pack(catalog, max_chars=10_000) == full_schema_pack(catalog)


def test_length_truncated_pack_rejects_unusable_budget(sample_database: Path) -> None:
    with pytest.raises(ValueError, match="too small"):
        length_truncated_schema_pack(extract_catalog(sample_database), max_chars=1)
