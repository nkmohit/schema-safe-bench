from pathlib import Path

import pytest

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.models import RetrievalHit, SchemaDocument
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
    assert all(set(hit.component_scores) == {"bm25", "dense"} for hit in hybrid_hits)
    assert all(set(hit.component_ranks) == {"bm25", "dense"} for hit in hybrid_hits)
    assert all(set(hit.component_contributions) == {"bm25", "dense"} for hit in hybrid_hits)
    assert all(
        hit.score == pytest.approx(sum(hit.component_contributions.values())) for hit in hybrid_hits
    )


class _StaticRetriever:
    def __init__(self, documents: list[SchemaDocument], hits: list[RetrievalHit]) -> None:
        self.documents = documents
        self.hits = hits

    def retrieve(self, question: str, *, top_k: int) -> list[RetrievalHit]:
        del question
        return self.hits[:top_k]


def test_hybrid_uses_complete_component_ranks_and_document_id_ties() -> None:
    documents = [
        SchemaDocument(document_id="column:t.a", table_name="t", column_name="a", text="a"),
        SchemaDocument(document_id="column:t.b", table_name="t", column_name="b", text="b"),
    ]
    lexical = _StaticRetriever(
        documents,
        [
            RetrievalHit(
                document_id="column:t.a", table_name="t", column_name="a", score=4.0, rank=1
            ),
            RetrievalHit(
                document_id="column:t.b", table_name="t", column_name="b", score=3.0, rank=2
            ),
        ],
    )
    dense = _StaticRetriever(
        documents,
        [
            RetrievalHit(
                document_id="column:t.b", table_name="t", column_name="b", score=0.9, rank=1
            ),
            RetrievalHit(
                document_id="column:t.a", table_name="t", column_name="a", score=0.8, rank=2
            ),
        ],
    )

    hits = HybridRetriever(lexical, dense, rank_constant=60).retrieve("question", top_k=2)

    assert [hit.document_id for hit in hits] == ["column:t.a", "column:t.b"]
    assert hits[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert hits[0].component_scores == {"bm25": 4.0, "dense": 0.8}
    assert hits[0].component_ranks == {"bm25": 1, "dense": 2}
    assert hits[0].component_contributions == pytest.approx({"bm25": 1 / 61, "dense": 1 / 62})


def test_hybrid_rejects_invalid_policy_inputs(sample_database: Path) -> None:
    documents = build_schema_documents(extract_catalog(sample_database))
    lexical = BM25Retriever(documents)
    dense = DenseRetriever(documents, _embed)

    with pytest.raises(ValueError, match="rank_constant"):
        HybridRetriever(lexical, dense, rank_constant=0)
    with pytest.raises(ValueError, match="same ordered document set"):
        HybridRetriever(lexical, DenseRetriever(list(reversed(documents)), _embed))
    duplicate_documents = [documents[0], documents[0]]
    with pytest.raises(ValueError, match="document IDs must be unique"):
        HybridRetriever(
            BM25Retriever(duplicate_documents), DenseRetriever(duplicate_documents, _embed)
        )


def test_dense_retrieval_uses_distinct_query_embedding_and_stable_ties(
    sample_database: Path,
) -> None:
    documents = build_schema_documents(extract_catalog(sample_database))
    seen_queries = []

    def documents_embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def query_embed(question: str) -> list[float]:
        seen_queries.append(question)
        return [1.0, 0.0]

    hits = DenseRetriever(documents, documents_embed, embed_query=query_embed).retrieve(
        "question only", top_k=4
    )

    assert seen_queries == ["question only"]
    assert [hit.document_id for hit in hits] == sorted(
        document.document_id for document in documents
    )[:4]
    assert all(hit.component_scores == {"dense": 1.0} for hit in hits)
    assert len(DenseRetriever(documents, documents_embed).document_embeddings_sha256) == 64


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
