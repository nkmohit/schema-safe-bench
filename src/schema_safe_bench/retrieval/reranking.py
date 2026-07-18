"""Revision-pinned local cross-encoder reranking."""

import hashlib
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from schema_safe_bench.models import (
    RerankerConfig,
    RerankingCandidate,
    RetrievalHit,
    SchemaDocument,
)


class CrossEncoderReranker:
    """Score public-question/schema-document pairs under a frozen local contract."""

    def __init__(self, config: RerankerConfig, *, allow_download: bool = False) -> None:
        try:
            import torch
            from sentence_transformers import CrossEncoder
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "reranking support is not installed; run `uv sync --extra dense --dev`"
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
        self._torch = torch
        self._model = CrossEncoder(
            config.model_id,
            max_length=config.max_length,
            device=config.device,
            cache_dir=str(config.cache_dir),
            trust_remote_code=config.trust_remote_code,
            revision=config.revision,
            local_files_only=config.local_files_only and not allow_download,
            automodel_args={"use_safetensors": True},
        )
        model_config = self._model.model.config
        if model_config.max_position_embeddings != config.max_length:
            raise ValueError("reranker maximum sequence length does not match config")
        if model_config.num_labels != 1:
            raise ValueError("reranker must produce exactly one relevance logit")
        self._verify_snapshot()

    def score(self, question: str, document_texts: list[str]) -> list[float]:
        if not question.strip():
            raise ValueError("reranker question must not be empty")
        if not document_texts:
            return []
        pairs = [(question, text) for text in document_texts]
        scores = self._model.predict(
            pairs,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            num_workers=0,
            activation_fct=self._torch.nn.Identity(),
            convert_to_numpy=True,
        )
        values = scores.tolist()
        return [float(value) for value in values]

    def _verify_snapshot(self) -> None:
        snapshot = _snapshot_path(self.config)
        expected = {
            "model.safetensors": self.config.weights_sha256,
            "tokenizer.json": self.config.tokenizer_sha256,
            "tokenizer_config.json": self.config.tokenizer_config_sha256,
            "special_tokens_map.json": self.config.special_tokens_sha256,
            "config.json": self.config.config_sha256,
        }
        for relative, digest in expected.items():
            path = snapshot / relative
            if not path.is_file() or _sha256(path) != digest:
                raise RuntimeError(
                    f"cached reranker model file failed provenance check: {relative}"
                )


def rerank_hits(
    question: str,
    documents: list[SchemaDocument],
    first_stage_hits: list[RetrievalHit],
    *,
    score: Callable[[str, list[str]], list[float]],
    top_k: int,
) -> tuple[list[RetrievalHit], list[RerankingCandidate]]:
    """Rerank a fixed B4 candidate list with stable, fully audited ordering."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if len({hit.document_id for hit in first_stage_hits}) != len(first_stage_hits):
        raise ValueError("reranker candidate document IDs must be unique")
    by_id = {document.document_id: document for document in documents}
    if any(hit.document_id not in by_id for hit in first_stage_hits):
        raise ValueError("reranker candidate is absent from the schema document set")
    ordered = sorted(first_stage_hits, key=lambda hit: hit.rank)
    if [hit.rank for hit in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("reranker candidates must have contiguous first-stage ranks")
    scores = score(question, [by_id[hit.document_id].text for hit in ordered])
    if len(scores) != len(ordered):
        raise ValueError("reranker must return exactly one score per candidate")
    ranked = sorted(
        zip(ordered, scores, strict=True),
        key=lambda item: (-item[1], item[0].rank, item[0].document_id),
    )
    candidates = [
        RerankingCandidate(
            document_id=hit.document_id,
            table_name=hit.table_name,
            column_name=hit.column_name,
            first_stage_score=hit.score,
            pre_rerank_rank=hit.rank,
            component_scores=hit.component_scores,
            component_ranks=hit.component_ranks,
            component_contributions=hit.component_contributions,
            reranker_score=reranker_score,
            post_rerank_rank=post_rank,
            selected=post_rank <= top_k,
        )
        for post_rank, (hit, reranker_score) in enumerate(ranked, start=1)
    ]
    selected = [
        RetrievalHit(
            document_id=candidate.document_id,
            table_name=candidate.table_name,
            column_name=candidate.column_name,
            score=candidate.reranker_score,
            rank=candidate.post_rerank_rank,
            component_scores=candidate.component_scores,
            component_ranks=candidate.component_ranks,
            component_contributions=candidate.component_contributions,
        )
        for candidate in candidates[:top_k]
    ]
    return selected, candidates


def cache_cross_encoder(config: RerankerConfig) -> CrossEncoderReranker:
    """Download the pinned snapshot, then verify its declared runtime files."""
    return CrossEncoderReranker(config, allow_download=True)


def _snapshot_path(config: RerankerConfig) -> Path:
    return (
        config.cache_dir
        / ("models--" + config.model_id.replace("/", "--"))
        / "snapshots"
        / config.revision
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
