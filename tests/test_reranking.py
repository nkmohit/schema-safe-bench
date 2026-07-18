import hashlib
import sys
from types import SimpleNamespace

import pytest

from schema_safe_bench.models import RerankerConfig, RetrievalHit, SchemaDocument
from schema_safe_bench.retrieval import reranking


class _Scores:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


def _config() -> RerankerConfig:
    return RerankerConfig(
        model_id="fixture/reranker",
        revision="a" * 40,
        weights_sha256="1" * 64,
        tokenizer_sha256="2" * 64,
        tokenizer_config_sha256="3" * 64,
        special_tokens_sha256="4" * 64,
        config_sha256="5" * 64,
    )


def _hits() -> tuple[list[SchemaDocument], list[RetrievalHit]]:
    documents = [
        SchemaDocument(document_id="column:t.b", table_name="t", column_name="b", text="doc b"),
        SchemaDocument(document_id="column:t.a", table_name="t", column_name="a", text="doc a"),
        SchemaDocument(document_id="table:t", table_name="t", text="doc table"),
    ]
    hits = [
        RetrievalHit(
            document_id=document.document_id,
            table_name=document.table_name,
            column_name=document.column_name,
            score=1.0 / rank,
            rank=rank,
            component_scores={"bm25": float(rank), "dense": 1.0 / rank},
            component_ranks={"bm25": rank, "dense": 4 - rank},
            component_contributions={"bm25": 0.01, "dense": 0.02},
        )
        for rank, document in enumerate(documents, start=1)
    ]
    return documents, hits


def test_cross_encoder_contract_freezes_pairs_batching_truncation_and_raw_logits(
    monkeypatch,
) -> None:
    calls = {}

    class FakeCrossEncoder:
        def __init__(self, model_id: str, **kwargs) -> None:
            calls["load"] = (model_id, kwargs)
            self.model = SimpleNamespace(
                config=SimpleNamespace(max_position_embeddings=512, num_labels=1)
            )

        @staticmethod
        def predict(pairs, **kwargs):
            calls["predict"] = (pairs, kwargs)
            return _Scores([0.25, -0.5])

    class Identity:
        pass

    torch = SimpleNamespace(
        set_num_threads=lambda value: calls.setdefault("threads", value),
        use_deterministic_algorithms=lambda value: calls.setdefault("deterministic", value),
        nn=SimpleNamespace(Identity=Identity),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(CrossEncoder=FakeCrossEncoder),
    )
    monkeypatch.setattr(reranking, "version", lambda _: "3.4.1")
    monkeypatch.setattr(reranking.CrossEncoderReranker, "_verify_snapshot", lambda _: None)

    model = reranking.CrossEncoderReranker(_config())
    scores = model.score("question", ["document one", "document two"])

    assert scores == [0.25, -0.5]
    assert calls["load"] == (
        "fixture/reranker",
        {
            "max_length": 512,
            "device": "cpu",
            "cache_dir": ".cache/schema-safe-bench/huggingface",
            "trust_remote_code": False,
            "revision": "a" * 40,
            "local_files_only": True,
            "automodel_args": {"use_safetensors": True},
        },
    )
    assert calls["threads"] == 1 and calls["deterministic"] is True
    pairs, kwargs = calls["predict"]
    assert pairs == [("question", "document one"), ("question", "document two")]
    assert kwargs["batch_size"] == 32
    assert kwargs["num_workers"] == 0
    assert isinstance(kwargs["activation_fct"], Identity)
    assert kwargs["convert_to_numpy"] is True


def test_reranking_preserves_every_b4_component_and_uses_stable_exact_ties() -> None:
    documents, hits = _hits()

    selected, candidates = reranking.rerank_hits(
        "question",
        documents,
        hits,
        score=lambda _question, _texts: [0.5, 0.5, 0.75],
        top_k=2,
    )

    assert [candidate.document_id for candidate in candidates] == [
        "table:t",
        "column:t.b",
        "column:t.a",
    ]
    assert [candidate.post_rerank_rank for candidate in candidates] == [1, 2, 3]
    assert [candidate.selected for candidate in candidates] == [True, True, False]
    assert [hit.document_id for hit in selected] == ["table:t", "column:t.b"]
    by_id = {hit.document_id: hit for hit in hits}
    for candidate in candidates:
        original = by_id[candidate.document_id]
        assert candidate.first_stage_score == original.score
        assert candidate.pre_rerank_rank == original.rank
        assert candidate.component_scores == original.component_scores
        assert candidate.component_ranks == original.component_ranks
        assert candidate.component_contributions == original.component_contributions


def test_reranking_rejects_incomplete_or_misaligned_scores() -> None:
    documents, hits = _hits()
    with pytest.raises(ValueError, match="exactly one score"):
        reranking.rerank_hits(
            "question", documents, hits, score=lambda _question, _texts: [1.0], top_k=1
        )
    with pytest.raises(ValueError, match="contiguous"):
        reranking.rerank_hits(
            "question",
            documents,
            [hits[0], hits[1].model_copy(update={"rank": 3})],
            score=lambda _question, _texts: [1.0, 0.0],
            top_k=1,
        )


def test_cached_reranker_hashes_are_enforced(tmp_path, monkeypatch) -> None:
    snapshot = tmp_path / "models--fixture--reranker" / "snapshots" / ("a" * 40)
    snapshot.mkdir(parents=True)
    payloads = {
        "model.safetensors": b"weights",
        "tokenizer.json": b"tokenizer",
        "tokenizer_config.json": b"tokenizer config",
        "special_tokens_map.json": b"special tokens",
        "config.json": b"config",
    }
    for name, payload in payloads.items():
        (snapshot / name).write_bytes(payload)
    config = _config().model_copy(
        update={
            "cache_dir": tmp_path,
            "weights_sha256": hashlib.sha256(payloads["model.safetensors"]).hexdigest(),
            "tokenizer_sha256": hashlib.sha256(payloads["tokenizer.json"]).hexdigest(),
            "tokenizer_config_sha256": hashlib.sha256(
                payloads["tokenizer_config.json"]
            ).hexdigest(),
            "special_tokens_sha256": hashlib.sha256(
                payloads["special_tokens_map.json"]
            ).hexdigest(),
            "config_sha256": hashlib.sha256(payloads["config.json"]).hexdigest(),
        }
    )

    class FakeCrossEncoder:
        def __init__(self, *_args, **_kwargs) -> None:
            self.model = SimpleNamespace(
                config=SimpleNamespace(max_position_embeddings=512, num_labels=1)
            )

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            set_num_threads=lambda _: None,
            use_deterministic_algorithms=lambda _: None,
            nn=SimpleNamespace(Identity=lambda: None),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(CrossEncoder=FakeCrossEncoder),
    )
    monkeypatch.setattr(reranking, "version", lambda _: "3.4.1")

    reranking.CrossEncoderReranker(config)
    (snapshot / "model.safetensors").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match=r"model\.safetensors"):
        reranking.CrossEncoderReranker(config)


def test_cache_reranker_allows_only_the_pinned_download(monkeypatch) -> None:
    loaded = {}

    class FakeCrossEncoder:
        def __init__(self, _model_id: str, **kwargs) -> None:
            loaded.update(kwargs)
            self.model = SimpleNamespace(
                config=SimpleNamespace(max_position_embeddings=512, num_labels=1)
            )

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            set_num_threads=lambda _: None,
            use_deterministic_algorithms=lambda _: None,
            nn=SimpleNamespace(Identity=lambda: None),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(CrossEncoder=FakeCrossEncoder),
    )
    monkeypatch.setattr(reranking, "version", lambda _: "3.4.1")
    monkeypatch.setattr(reranking.CrossEncoderReranker, "_verify_snapshot", lambda _: None)

    reranking.cache_cross_encoder(_config())

    assert loaded["revision"] == "a" * 40
    assert loaded["local_files_only"] is False
