import hashlib
import sys
from types import SimpleNamespace

import pytest

from schema_safe_bench.models import DenseEmbeddingConfig
from schema_safe_bench.retrieval import embeddings


class _Vectors:
    def __init__(self, values: list[list[float]]) -> None:
        self.values = values

    def tolist(self) -> list[list[float]]:
        return self.values


def _config() -> DenseEmbeddingConfig:
    return DenseEmbeddingConfig(
        model_id="fixture/model",
        revision="a" * 40,
        query_prefix="query: ",
        max_seq_length=512,
        embedding_dimension=384,
        weights_sha256="1" * 64,
        tokenizer_sha256="2" * 64,
        config_sha256="3" * 64,
    )


def test_sentence_transformer_contract_is_frozen(monkeypatch) -> None:
    calls = {}

    class FakeModel:
        max_seq_length = 512

        def __init__(self, model_id: str, **kwargs) -> None:
            calls["load"] = (model_id, kwargs)

        @staticmethod
        def get_sentence_embedding_dimension() -> int:
            return 384

        @staticmethod
        def encode(texts: list[str], **kwargs) -> _Vectors:
            calls.setdefault("encode", []).append((texts, kwargs))
            return _Vectors([[float(index), 1.0] for index, _ in enumerate(texts)])

    torch = SimpleNamespace(
        set_num_threads=lambda value: calls.setdefault("threads", value),
        use_deterministic_algorithms=lambda value: calls.setdefault("deterministic", value),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel),
    )
    monkeypatch.setattr(embeddings, "version", lambda _: "3.4.1")
    monkeypatch.setattr(embeddings.SentenceTransformerEmbedder, "_verify_snapshot", lambda _: None)

    embedder = embeddings.SentenceTransformerEmbedder(_config())
    documents = embedder.embed_documents(["doc one", "doc two"])
    query = embedder.embed_query("find it")

    assert calls["load"][0] == "fixture/model"
    assert calls["load"][1]["revision"] == "a" * 40
    assert calls["load"][1]["local_files_only"] is True
    assert calls["threads"] == 1 and calls["deterministic"] is True
    assert documents == [[0.0, 1.0], [1.0, 1.0]]
    assert query == [0.0, 1.0]
    assert calls["encode"][1][0] == ["query: find it"]
    assert calls["encode"][1][1] == {
        "batch_size": 32,
        "show_progress_bar": False,
        "convert_to_numpy": True,
        "normalize_embeddings": True,
        "precision": "float32",
    }


def test_cache_model_allows_only_the_pinned_download(monkeypatch) -> None:
    loaded = {}

    class FakeModel:
        max_seq_length = 512

        def __init__(self, _model_id: str, **kwargs) -> None:
            loaded.update(kwargs)

        @staticmethod
        def get_sentence_embedding_dimension() -> int:
            return 384

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            set_num_threads=lambda _: None, use_deterministic_algorithms=lambda _: None
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel),
    )
    monkeypatch.setattr(embeddings, "version", lambda _: "3.4.1")
    monkeypatch.setattr(embeddings.SentenceTransformerEmbedder, "_verify_snapshot", lambda _: None)

    embeddings.cache_sentence_transformer(_config())

    assert loaded["revision"] == "a" * 40
    assert loaded["local_files_only"] is False


def test_cached_snapshot_hashes_are_enforced(tmp_path, monkeypatch) -> None:
    snapshot = tmp_path / "models--fixture--model" / "snapshots" / ("a" * 40)
    snapshot.mkdir(parents=True)
    payloads = {
        "model.safetensors": b"weights",
        "tokenizer.json": b"tokenizer",
        "config.json": b"config",
    }
    for name, payload in payloads.items():
        (snapshot / name).write_bytes(payload)
    config = _config().model_copy(
        update={
            "cache_dir": tmp_path,
            "weights_sha256": hashlib.sha256(payloads["model.safetensors"]).hexdigest(),
            "tokenizer_sha256": hashlib.sha256(payloads["tokenizer.json"]).hexdigest(),
            "config_sha256": hashlib.sha256(payloads["config.json"]).hexdigest(),
        }
    )

    class FakeModel:
        max_seq_length = 512

        def __init__(self, _model_id: str, **_kwargs) -> None:
            pass

        @staticmethod
        def get_sentence_embedding_dimension() -> int:
            return 384

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            set_num_threads=lambda _: None, use_deterministic_algorithms=lambda _: None
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel),
    )
    monkeypatch.setattr(embeddings, "version", lambda _: "3.4.1")

    embeddings.SentenceTransformerEmbedder(config)
    (snapshot / "model.safetensors").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match=r"model\.safetensors"):
        embeddings.SentenceTransformerEmbedder(config)
