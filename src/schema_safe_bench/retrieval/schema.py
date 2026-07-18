"""Deterministic schema retrieval baselines."""

import math
import re
from collections.abc import Callable

from rank_bm25 import BM25Okapi

from schema_safe_bench.models import (
    Catalog,
    RetrievalHit,
    SchemaDocument,
    SchemaPack,
    SchemaPackTable,
)

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
EmbeddingFunction = Callable[[list[str]], list[list[float]]]


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def build_schema_documents(catalog: Catalog) -> list[SchemaDocument]:
    """Create one table document and one document per column."""
    documents: list[SchemaDocument] = []
    for table in catalog.tables:
        column_summary = ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
        documents.append(
            SchemaDocument(
                document_id=f"table:{table.name}",
                table_name=table.name,
                text=f"table {table.name}; columns {column_summary}",
            )
        )
        for column in table.columns:
            key_text = " primary key" if column.primary_key_position else ""
            documents.append(
                SchemaDocument(
                    document_id=f"column:{table.name}.{column.name}",
                    table_name=table.name,
                    column_name=column.name,
                    text=(
                        f"table {table.name}; column {column.name}; "
                        f"type {column.data_type}{key_text}"
                    ),
                )
            )
    return documents


class BM25Retriever:
    def __init__(
        self,
        documents: list[SchemaDocument],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        if not documents:
            raise ValueError("at least one schema document is required")
        if k1 <= 0 or not 0 <= b <= 1 or epsilon < 0:
            raise ValueError("invalid BM25 parameters")
        self.documents = documents
        self._index = BM25Okapi(
            [_tokens(document.text) for document in documents],
            k1=k1,
            b=b,
            epsilon=epsilon,
        )

    def retrieve(self, question: str, *, top_k: int) -> list[RetrievalHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        scores = self._index.get_scores(_tokens(question))
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (-float(item[1]), self.documents[item[0]].document_id),
        )[:top_k]
        return [
            RetrievalHit(
                document_id=self.documents[index].document_id,
                table_name=self.documents[index].table_name,
                column_name=self.documents[index].column_name,
                score=float(score),
                rank=rank,
                component_scores={"bm25": float(score)},
            )
            for rank, (index, score) in enumerate(ranked, start=1)
        ]


class DenseRetriever:
    """Dense retrieval with an injected, versioned embedding function."""

    def __init__(self, documents: list[SchemaDocument], embed: EmbeddingFunction) -> None:
        if not documents:
            raise ValueError("at least one schema document is required")
        self.documents = documents
        self._embed = embed
        self._vectors = embed([document.text for document in documents])
        if len(self._vectors) != len(documents):
            raise ValueError("embedding function returned the wrong vector count")

    def retrieve(self, question: str, *, top_k: int) -> list[RetrievalHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vectors = self._embed([question])
        if len(query_vectors) != 1:
            raise ValueError("embedding function must return one query vector")
        query = query_vectors[0]
        scored = [(index, _cosine(query, vector)) for index, vector in enumerate(self._vectors)]
        ranked = sorted(scored, key=lambda item: (-item[1], self.documents[item[0]].document_id))[
            :top_k
        ]
        return [
            RetrievalHit(
                document_id=self.documents[index].document_id,
                table_name=self.documents[index].table_name,
                column_name=self.documents[index].column_name,
                score=score,
                rank=rank,
                component_scores={"dense": score},
            )
            for rank, (index, score) in enumerate(ranked, start=1)
        ]


class HybridRetriever:
    """Fuse lexical and dense ranks with weighted reciprocal rank fusion."""

    def __init__(
        self,
        lexical: BM25Retriever,
        dense: DenseRetriever,
        *,
        lexical_weight: float = 0.5,
        dense_weight: float = 0.5,
        rank_constant: int = 60,
    ) -> None:
        if lexical_weight < 0 or dense_weight < 0 or lexical_weight + dense_weight == 0:
            raise ValueError("retrieval weights must be non-negative with a positive sum")
        self.lexical = lexical
        self.dense = dense
        self.lexical_weight = lexical_weight
        self.dense_weight = dense_weight
        self.rank_constant = rank_constant

    def retrieve(self, question: str, *, top_k: int) -> list[RetrievalHit]:
        candidate_k = min(len(self.lexical.documents), max(top_k * 4, top_k))
        sources = {
            "bm25": (self.lexical.retrieve(question, top_k=candidate_k), self.lexical_weight),
            "dense": (self.dense.retrieve(question, top_k=candidate_k), self.dense_weight),
        }
        by_id: dict[str, RetrievalHit] = {}
        fused: dict[str, float] = {}
        components: dict[str, dict[str, float]] = {}
        for source, (hits, weight) in sources.items():
            for hit in hits:
                by_id.setdefault(hit.document_id, hit)
                fused[hit.document_id] = fused.get(hit.document_id, 0.0) + weight / (
                    self.rank_constant + hit.rank
                )
                components.setdefault(hit.document_id, {})[source] = hit.score
        ranked_ids = sorted(fused, key=lambda item: (-fused[item], item))[:top_k]
        return [
            RetrievalHit(
                document_id=document_id,
                table_name=by_id[document_id].table_name,
                column_name=by_id[document_id].column_name,
                score=fused[document_id],
                rank=rank,
                component_scores=components[document_id],
            )
            for rank, document_id in enumerate(ranked_ids, start=1)
        ]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def full_schema_pack(catalog: Catalog, *, max_chars: int | None = None) -> SchemaPack:
    return build_schema_pack(catalog, hits=[], include_all=True, max_chars=max_chars)


def length_truncated_schema_pack(catalog: Catalog, *, max_chars: int) -> SchemaPack:
    """Build a deterministic catalog prefix without partial schema declarations."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    full = full_schema_pack(catalog)
    if len(full.serialized) <= max_chars:
        return full

    included: list[SchemaPackTable] = []
    stopped = False
    for table in catalog.tables:
        visible_columns = []
        for column in table.columns:
            candidate_columns = [*visible_columns, column]
            candidate_tables = [
                *included,
                SchemaPackTable(name=table.name, columns=candidate_columns),
            ]
            candidate_foreign_keys = _visible_foreign_keys(catalog, candidate_tables)
            if len(_serialize_schema(candidate_tables, candidate_foreign_keys)) > max_chars:
                stopped = True
                break
            visible_columns = candidate_columns
        if visible_columns:
            included.append(SchemaPackTable(name=table.name, columns=visible_columns))
        if stopped:
            break

    if not included:
        raise ValueError("max_chars is too small for the first schema declaration")
    foreign_keys = _visible_foreign_keys(catalog, included)
    serialized = _serialize_schema(included, foreign_keys)
    return SchemaPack(
        tables=included,
        foreign_keys=foreign_keys,
        retrieval_hits=[],
        serialized=serialized,
    )


def _visible_foreign_keys(catalog: Catalog, tables: list[SchemaPackTable]) -> list[str]:
    visible_columns = {table.name: {column.name for column in table.columns} for table in tables}
    return sorted(
        {
            f"{table.name}.{foreign_key.from_column} -> "
            f"{foreign_key.to_table}.{foreign_key.to_column}"
            for table in catalog.tables
            if table.name in visible_columns
            for foreign_key in table.foreign_keys
            if foreign_key.to_table in visible_columns
            and foreign_key.from_column in visible_columns[table.name]
            and foreign_key.to_column in visible_columns[foreign_key.to_table]
        }
    )


def _serialize_schema(tables: list[SchemaPackTable], foreign_keys: list[str]) -> str:
    lines = []
    for table in tables:
        columns_text = ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
        lines.append(f"{table.name}({columns_text})")
    lines.extend(f"FK {foreign_key}" for foreign_key in foreign_keys)
    return "\n".join(lines)


def build_schema_pack(
    catalog: Catalog,
    hits: list[RetrievalHit],
    *,
    include_all: bool = False,
    max_chars: int | None = None,
) -> SchemaPack:
    """Serialize selected tables and columns plus join edges between selected tables."""
    if include_all:
        selected_tables = {table.name for table in catalog.tables}
    else:
        selected_tables = {hit.table_name for hit in hits}
    selected_columns: dict[str, set[str]] = {}
    for hit in hits:
        if hit.column_name:
            selected_columns.setdefault(hit.table_name, set()).add(hit.column_name)

    foreign_keys = sorted(
        {
            f"{table.name}.{foreign_key.from_column} -> "
            f"{foreign_key.to_table}.{foreign_key.to_column}"
            for table in catalog.tables
            if table.name in selected_tables
            for foreign_key in table.foreign_keys
            if foreign_key.to_table in selected_tables
        }
    )
    join_columns: dict[str, set[str]] = {}
    for table in catalog.tables:
        if table.name not in selected_tables:
            continue
        for foreign_key in table.foreign_keys:
            if foreign_key.to_table not in selected_tables:
                continue
            join_columns.setdefault(table.name, set()).add(foreign_key.from_column)
            join_columns.setdefault(foreign_key.to_table, set()).add(foreign_key.to_column)

    pack_tables: list[SchemaPackTable] = []
    for table in catalog.tables:
        if not include_all and table.name not in selected_tables:
            continue
        columns = table.columns
        chosen = selected_columns.get(table.name)
        if chosen and not any(
            hit.table_name == table.name and hit.column_name is None for hit in hits
        ):
            required_columns = chosen | join_columns.get(table.name, set())
            columns = [
                column
                for column in columns
                if column.name in required_columns or column.primary_key_position > 0
            ]
        pack_tables.append(SchemaPackTable(name=table.name, columns=columns))
    serialized = _serialize_schema(pack_tables, foreign_keys)
    if max_chars is not None:
        serialized = serialized[:max_chars]
    return SchemaPack(
        tables=pack_tables,
        foreign_keys=foreign_keys,
        retrieval_hits=hits,
        serialized=serialized,
    )
