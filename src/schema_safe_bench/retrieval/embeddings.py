"""Revision-pinned local sentence-transformer embeddings."""

import hashlib
from importlib.metadata import version
from pathlib import Path

from schema_safe_bench.models import DenseEmbeddingConfig


class SentenceTransformerEmbedder:
    """Encode schema documents and questions under a frozen local contract."""

    def __init__(self, config: DenseEmbeddingConfig, *, allow_download: bool = False) -> None:
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "dense retrieval support is not installed; run `uv sync --extra dense --dev`"
            ) from exc
        torch.set_num_threads(config.torch_num_threads)
        torch.use_deterministic_algorithms(config.deterministic_algorithms)
        self.config = config
        self.library_version = version("sentence-transformers")
        self.dependency_versions = {
            package: version(package)
            for package in (
                "huggingface-hub",
                "sentence-transformers",
                "tokenizers",
                "torch",
                "transformers",
            )
        }
        self._model = SentenceTransformer(
            config.model_id,
            revision=config.revision,
            cache_folder=str(config.cache_dir),
            device=config.device,
            trust_remote_code=config.trust_remote_code,
            local_files_only=config.local_files_only and not allow_download,
        )
        if self._model.max_seq_length != config.max_seq_length:
            raise ValueError("embedding model maximum sequence length does not match config")
        if self._model.get_sentence_embedding_dimension() != config.embedding_dimension:
            raise ValueError("embedding model dimension does not match config")
        self._verify_snapshot()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, question: str) -> list[float]:
        return self._encode([self.config.query_prefix + question])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize_embeddings,
            precision=self.config.precision,
        )
        return vectors.tolist()

    def _verify_snapshot(self) -> None:
        snapshot = (
            self.config.cache_dir
            / ("models--" + self.config.model_id.replace("/", "--"))
            / "snapshots"
            / self.config.revision
        )
        expected = {
            "model.safetensors": self.config.weights_sha256,
            "tokenizer.json": self.config.tokenizer_sha256,
            "config.json": self.config.config_sha256,
        }
        for relative, digest in expected.items():
            path = snapshot / relative
            if not path.is_file() or _sha256(path) != digest:
                raise RuntimeError(
                    f"cached embedding model file failed provenance check: {relative}"
                )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_sentence_transformer(config: DenseEmbeddingConfig) -> SentenceTransformerEmbedder:
    """Download the pinned snapshot, then verify its declared dimensions."""
    return SentenceTransformerEmbedder(config, allow_download=True)
