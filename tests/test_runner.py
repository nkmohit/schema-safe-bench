import json
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.generation import (
    load_recording,
    request_sha256,
    save_record,
)
from schema_safe_bench.models import (
    GenerationResponse,
    HostedRunConfig,
    SmokeRunConfig,
)
from schema_safe_bench.prompting import build_generation_request
from schema_safe_bench.reporting import write_run_artifacts
from schema_safe_bench.retrieval import (
    build_schema_documents,
    full_schema_pack,
    length_truncated_schema_pack,
)
from schema_safe_bench.runner import (
    _hosted_schema_pack,
    load_hosted_run_config,
    load_run_config,
    run_hosted_smoke,
    run_offline_smoke,
)


def _run_inputs(sample_database: Path, tmp_path: Path) -> SmokeRunConfig:
    databases = tmp_path / "databases" / "shop"
    databases.mkdir(parents=True)
    (databases / "shop.sqlite").write_bytes(sample_database.read_bytes())
    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "List customer names",
                    "SQL": "SELECT name FROM customers ORDER BY name",
                },
                {
                    "question_id": 2,
                    "db_id": "shop",
                    "question": "Unsafe request",
                    "SQL": "SELECT count(*) FROM orders",
                },
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset": "bird-minidev-select",
                "dataset_revision": "fixture",
                "selection": "fixture",
                "seed": 1,
                "task_ids": ["1", "2"],
            }
        ),
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps({"1": "SELECT name FROM customers ORDER BY name", "2": "ABSTAIN"}),
        encoding="utf-8",
    )
    return SmokeRunConfig(
        run_id="fixture-run",
        method_id="B0",
        tasks_path=tasks,
        databases_root=tmp_path / "databases",
        manifest_path=manifest,
        predictions_path=predictions,
        output_path=tmp_path / "results" / "trace.jsonl",
    )


def test_offline_smoke_runs_end_to_end(sample_database: Path, tmp_path: Path) -> None:
    config = _run_inputs(sample_database, tmp_path)
    traces, summary = run_offline_smoke(config)

    assert summary.tasks == 2
    assert summary.correct == 1
    assert summary.abstained == 1
    assert traces[0].comparison and traces[0].comparison.equivalent
    assert traces[1].failure_label == "safe_abstention"

    trace_path, summary_path = write_run_artifacts(traces, summary, config.output_path)
    assert len(trace_path.read_text().splitlines()) == 2
    assert json.loads(summary_path.read_text())["correct"] == 1


def test_run_outputs_cannot_be_overwritten(sample_database: Path, tmp_path: Path) -> None:
    config = _run_inputs(sample_database, tmp_path)
    traces, summary = run_offline_smoke(config)
    write_run_artifacts(traces, summary, config.output_path)

    try:
        write_run_artifacts(traces, summary, config.output_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing trace should not be overwritten")


def test_load_run_config(tmp_path: Path) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "run_id": "r",
                "method_id": "B2",
                "tasks_path": "tasks.json",
                "databases_root": "db",
                "manifest_path": "manifest.json",
                "predictions_path": "predictions.json",
                "output_path": "result.jsonl",
            }
        ),
        encoding="utf-8",
    )
    assert load_run_config(config_path).method_id == "B2"


def test_hosted_smoke_replays_without_api_access(sample_database: Path, tmp_path: Path) -> None:
    config = _run_inputs(sample_database, tmp_path)
    hosted = HostedRunConfig(
        run_id="hosted-fixture",
        method_id="B0",
        tasks_path=config.tasks_path,
        databases_root=config.databases_root,
        manifest_path=config.manifest_path,
        recording_path=tmp_path / "recording.json",
        output_path=tmp_path / "hosted" / "trace.jsonl",
    )
    tasks_payload = json.loads(config.tasks_path.read_text())
    recording = load_recording(hosted.recording_path, model_name=hosted.model.model_name)
    for record in tasks_payload:
        task_id = str(record["question_id"])
        database = hosted.databases_root / "shop" / "shop.sqlite"
        schema_pack = full_schema_pack(extract_catalog(database, db_id="shop"))
        request = build_generation_request(
            question=record["question"],
            schema_pack=schema_pack,
            model_name=hosted.model.model_name,
            temperature=hosted.model.temperature,
            max_output_tokens=hosted.model.max_output_tokens,
            reasoning_effort=hosted.model.reasoning_effort,
        )
        digest = request_sha256(task_id, request)
        output = record["SQL"]
        save_record(
            recording,
            hosted.recording_path,
            task_id=task_id,
            digest=digest,
            response=GenerationResponse(
                raw_output=output,
                model_name="gpt-5.6-luna",
                requested_model_name="gpt-5.6-luna",
                provider="openai",
                endpoint="responses",
                status="completed",
                input_tokens=10,
                output_tokens=5,
                estimated_cost_usd=0.00004,
            ),
        )

    traces, summary = run_hosted_smoke(hosted, replay_only=True)
    assert summary.tasks == summary.correct == 2
    assert summary.input_tokens == 20
    assert all(trace.generation and trace.generation.replayed for trace in traces)
    assert all(trace.request_sha256 for trace in traces)
    assert all(trace.configuration_sha256 for trace in traces)
    assert all(trace.software_revision for trace in traces)
    assert all(trace.schema_pack for trace in traces)


def test_load_hosted_config_records_luna_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "hosted.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "run_id": "hosted",
                "method_id": "B0",
                "tasks_path": "tasks.json",
                "databases_root": "db",
                "manifest_path": "manifest.json",
                "recording_path": "recording.json",
                "output_path": "trace.jsonl",
                "model": {"model_name": "gpt-5.6-luna", "store": False},
                "budget": {"project_limit_usd": 95.0, "run_limit_usd": 5.0},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_hosted_run_config(config_path)
    assert loaded.model.model_name == "gpt-5.6-luna"
    assert loaded.model.store is False
    assert loaded.budget.project_limit_usd < 100


def test_hosted_b1_replays_with_length_truncated_schema(
    sample_database: Path, tmp_path: Path
) -> None:
    config = _run_inputs(sample_database, tmp_path)
    hosted = HostedRunConfig(
        run_id="hosted-b1-fixture",
        method_id="B1",
        tasks_path=config.tasks_path,
        databases_root=config.databases_root,
        manifest_path=config.manifest_path,
        recording_path=tmp_path / "b1-recording.json",
        output_path=tmp_path / "b1" / "trace.jsonl",
        schema_context={
            "strategy": "length_truncated",
            "max_chars": 80,
            "policy_id": "catalog-character-prefix-v1",
        },
    )
    recording = load_recording(hosted.recording_path, model_name=hosted.model.model_name)
    database = hosted.databases_root / "shop" / "shop.sqlite"
    schema_pack = length_truncated_schema_pack(
        extract_catalog(database, db_id="shop"), max_chars=80
    )
    for record in json.loads(config.tasks_path.read_text()):
        task_id = str(record["question_id"])
        request = build_generation_request(
            question=record["question"],
            schema_pack=schema_pack,
            model_name=hosted.model.model_name,
            temperature=hosted.model.temperature,
            max_output_tokens=hosted.model.max_output_tokens,
            reasoning_effort=hosted.model.reasoning_effort,
        )
        save_record(
            recording,
            hosted.recording_path,
            task_id=task_id,
            digest=request_sha256(task_id, request),
            response=GenerationResponse(
                raw_output=record["SQL"],
                model_name="gpt-5.6-luna",
                requested_model_name="gpt-5.6-luna",
                provider="openai",
                endpoint="responses",
                status="completed",
            ),
        )

    traces, summary = run_hosted_smoke(hosted, replay_only=True)
    assert summary.method_id == "B1"
    assert summary.correct == 2
    assert all(trace.schema_pack == schema_pack for trace in traces)
    assert all(len(trace.schema_pack.serialized) <= 80 for trace in traces if trace.schema_pack)


def test_hosted_method_and_schema_context_must_match() -> None:
    common = {
        "run_id": "mismatch",
        "tasks_path": "tasks.json",
        "databases_root": "db",
        "manifest_path": "manifest.json",
        "recording_path": "recording.json",
        "output_path": "trace.jsonl",
    }
    with pytest.raises(ValueError, match="B1 requires"):
        HostedRunConfig(method_id="B1", **common)
    with pytest.raises(ValueError, match="B0 requires"):
        HostedRunConfig(
            method_id="B0",
            schema_context={
                "strategy": "length_truncated",
                "max_chars": 1000,
                "policy_id": "catalog-character-prefix-v1",
            },
            **common,
        )
    with pytest.raises(ValueError, match="B2 requires"):
        HostedRunConfig(method_id="B2", **common)
    with pytest.raises(ValueError, match="B3 requires"):
        HostedRunConfig(method_id="B3", **common)
    with pytest.raises(ValueError, match="B4 requires"):
        HostedRunConfig(method_id="B4", **common)


class _FakeDenseEmbedder:
    library_version = "fixture"
    dependency_versions: ClassVar[dict[str, str]] = {"sentence-transformers": "fixture"}

    @staticmethod
    def embed_documents(texts: list[str]) -> list[list[float]]:
        return [
            [
                float("customer" in text.casefold()),
                float("order" in text.casefold()),
                1.0,
            ]
            for text in texts
        ]

    @staticmethod
    def embed_query(question: str) -> list[float]:
        return [
            float("customer" in question.casefold()),
            float("order" in question.casefold()),
            1.0,
        ]


def _b3_hosted(base: SmokeRunConfig, tmp_path: Path) -> HostedRunConfig:
    return HostedRunConfig(
        run_id="hosted-b3-fixture",
        method_id="B3",
        tasks_path=base.tasks_path,
        databases_root=base.databases_root,
        manifest_path=base.manifest_path,
        recording_path=tmp_path / "b3-recording.json",
        output_path=tmp_path / "b3" / "trace.jsonl",
        schema_context={
            "strategy": "dense",
            "policy_id": "bge-dense-schema-documents-v1",
            "top_k": 12,
            "embedding": {
                "model_id": "fixture/model",
                "revision": "a" * 40,
                "query_prefix": "query: ",
                "embedding_dimension": 384,
                "weights_sha256": "1" * 64,
                "tokenizer_sha256": "2" * 64,
                "config_sha256": "3" * 64,
            },
        },
    )


def _b4_hosted(base: SmokeRunConfig, tmp_path: Path) -> HostedRunConfig:
    b3 = _b3_hosted(base, tmp_path)
    assert b3.schema_context and b3.schema_context.embedding
    return HostedRunConfig(
        run_id="hosted-b4-fixture",
        method_id="B4",
        tasks_path=base.tasks_path,
        databases_root=base.databases_root,
        manifest_path=base.manifest_path,
        recording_path=tmp_path / "b4-recording.json",
        output_path=tmp_path / "b4" / "trace.jsonl",
        schema_context={
            "strategy": "hybrid",
            "policy_id": "bm25-bge-rrf-schema-documents-v1",
            "top_k": 12,
            "k1": 1.5,
            "b": 0.75,
            "epsilon": 0.25,
            "candidate_depth": "all_documents",
            "lexical_weight": 1.0,
            "dense_weight": 1.0,
            "rank_constant": 60,
            "embedding": b3.schema_context.embedding.model_dump(mode="json"),
        },
    )


def test_b3_context_records_embedding_contract_and_reuses_document_vectors(
    sample_database: Path, tmp_path: Path
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    config = _b3_hosted(base, tmp_path)
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    cache = {}
    embedder = _FakeDenseEmbedder()

    first = _hosted_schema_pack(
        config,
        catalog=catalog,
        question="List customer names",
        dense_embedder=embedder,
        dense_retrievers=cache,
    )
    second = _hosted_schema_pack(
        config,
        catalog=catalog,
        question="List customer names",
        dense_embedder=embedder,
        dense_retrievers=cache,
    )

    assert first == second
    assert len(cache) == 1
    assert first.retrieval_metadata
    assert first.retrieval_metadata.embedding_model_id == "fixture/model"
    assert first.retrieval_metadata.embedding_model_revision == "a" * 40
    assert len(first.retrieval_metadata.document_embeddings_sha256) == 64
    assert len(first.retrieval_metadata.query_embedding_sha256) == 64
    assert [hit.rank for hit in first.retrieval_hits] == list(
        range(1, len(first.retrieval_hits) + 1)
    )


def test_hosted_b3_replay_does_not_use_reference_sql_for_retrieval(
    sample_database: Path, tmp_path: Path, monkeypatch
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    hosted = _b3_hosted(base, tmp_path)
    monkeypatch.setattr(
        "schema_safe_bench.runner.SentenceTransformerEmbedder", lambda _: _FakeDenseEmbedder()
    )
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    cache = {}
    recording = load_recording(hosted.recording_path, model_name=hosted.model.model_name)
    for record in json.loads(base.tasks_path.read_text()):
        task_id = str(record["question_id"])
        pack = _hosted_schema_pack(
            hosted,
            catalog=catalog,
            question=record["question"],
            dense_embedder=_FakeDenseEmbedder(),
            dense_retrievers=cache,
        )
        request = build_generation_request(
            question=record["question"],
            schema_pack=pack,
            model_name=hosted.model.model_name,
            temperature=hosted.model.temperature,
            max_output_tokens=hosted.model.max_output_tokens,
            reasoning_effort=hosted.model.reasoning_effort,
        )
        save_record(
            recording,
            hosted.recording_path,
            task_id=task_id,
            digest=request_sha256(task_id, request),
            response=GenerationResponse(
                raw_output=record["SQL"],
                model_name="gpt-5.6-luna",
                requested_model_name="gpt-5.6-luna",
                provider="openai",
                endpoint="responses",
                status="completed",
            ),
        )
    tasks = json.loads(base.tasks_path.read_text())
    tasks[0]["SQL"] = "SELECT customer_id FROM customers ORDER BY customer_id"
    tasks[0]["evidence"] = "changed evaluator-only clue"
    base.tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

    traces, summary = run_hosted_smoke(hosted, replay_only=True)

    assert summary.tasks == 2
    assert all(trace.generation and trace.generation.replayed for trace in traces)
    assert all(trace.schema_pack and trace.schema_pack.retrieval_metadata for trace in traces)


def test_b4_context_records_fusion_contract_and_complete_components(
    sample_database: Path, tmp_path: Path
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    config = _b4_hosted(base, tmp_path)
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    cache = {}

    pack = _hosted_schema_pack(
        config,
        catalog=catalog,
        question="List customer names",
        dense_embedder=_FakeDenseEmbedder(),
        dense_retrievers=cache,
    )

    assert len(cache) == 1
    assert pack.retrieval_metadata
    assert pack.retrieval_metadata.strategy == "hybrid"
    assert pack.retrieval_metadata.fusion_algorithm == "weighted-reciprocal-rank-fusion"
    assert pack.retrieval_metadata.fusion_candidate_depth == "all_documents"
    assert pack.retrieval_metadata.fusion_rank_constant == 60
    assert pack.retrieval_metadata.bm25_k1 == 1.5
    assert all(set(hit.component_scores) == {"bm25", "dense"} for hit in pack.retrieval_hits)
    assert all(set(hit.component_ranks) == {"bm25", "dense"} for hit in pack.retrieval_hits)
    assert all(set(hit.component_contributions) == {"bm25", "dense"} for hit in pack.retrieval_hits)


def test_hosted_b4_replay_does_not_use_evaluator_inputs_for_fusion(
    sample_database: Path, tmp_path: Path, monkeypatch
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    hosted = _b4_hosted(base, tmp_path)
    monkeypatch.setattr(
        "schema_safe_bench.runner.SentenceTransformerEmbedder", lambda _: _FakeDenseEmbedder()
    )
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    cache = {}
    recording = load_recording(hosted.recording_path, model_name=hosted.model.model_name)
    original_packs = {}
    for record in json.loads(base.tasks_path.read_text()):
        task_id = str(record["question_id"])
        pack = _hosted_schema_pack(
            hosted,
            catalog=catalog,
            question=record["question"],
            dense_embedder=_FakeDenseEmbedder(),
            dense_retrievers=cache,
        )
        original_packs[task_id] = pack
        request = build_generation_request(
            question=record["question"],
            schema_pack=pack,
            model_name=hosted.model.model_name,
            temperature=hosted.model.temperature,
            max_output_tokens=hosted.model.max_output_tokens,
            reasoning_effort=hosted.model.reasoning_effort,
        )
        save_record(
            recording,
            hosted.recording_path,
            task_id=task_id,
            digest=request_sha256(task_id, request),
            response=GenerationResponse(
                raw_output=record["SQL"],
                model_name="gpt-5.6-luna",
                requested_model_name="gpt-5.6-luna",
                provider="openai",
                endpoint="responses",
                status="completed",
            ),
        )
    tasks = json.loads(base.tasks_path.read_text())
    for task in tasks:
        task["SQL"] = "SELECT count(*) FROM orders"
        task["evidence"] = "changed evaluator-only input"
    base.tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

    traces, summary = run_hosted_smoke(hosted, replay_only=True)

    assert summary.tasks == 2
    assert all(trace.generation and trace.generation.replayed for trace in traces)
    assert all(trace.schema_pack == original_packs[trace.task_id] for trace in traces)


def test_b2_context_depends_only_on_question_and_catalog(
    sample_database: Path, tmp_path: Path
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    config = HostedRunConfig(
        run_id="hosted-b2-fixture",
        method_id="B2",
        tasks_path=base.tasks_path,
        databases_root=base.databases_root,
        manifest_path=base.manifest_path,
        recording_path=tmp_path / "recording.json",
        output_path=tmp_path / "trace.jsonl",
        schema_context={
            "strategy": "bm25",
            "policy_id": "bm25-schema-documents-v1",
            "top_k": 12,
            "k1": 1.5,
            "b": 0.75,
            "epsilon": 0.25,
        },
    )
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")

    first = _hosted_schema_pack(config, catalog=catalog, question="List customer names")
    second = _hosted_schema_pack(config, catalog=catalog, question="List customer names")

    assert first == second
    assert len(first.retrieval_hits) == min(12, len(build_schema_documents(catalog)))
    assert [hit.rank for hit in first.retrieval_hits] == list(
        range(1, len(first.retrieval_hits) + 1)
    )


def test_hosted_b2_replays_with_ranked_schema_evidence(
    sample_database: Path, tmp_path: Path
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    hosted = HostedRunConfig(
        run_id="hosted-b2-replay",
        method_id="B2",
        tasks_path=base.tasks_path,
        databases_root=base.databases_root,
        manifest_path=base.manifest_path,
        recording_path=tmp_path / "b2-recording.json",
        output_path=tmp_path / "b2" / "trace.jsonl",
        schema_context={
            "strategy": "bm25",
            "policy_id": "bm25-schema-documents-v1",
            "top_k": 12,
            "k1": 1.5,
            "b": 0.75,
            "epsilon": 0.25,
        },
    )
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    recording = load_recording(hosted.recording_path, model_name=hosted.model.model_name)
    for record in json.loads(base.tasks_path.read_text()):
        task_id = str(record["question_id"])
        pack = _hosted_schema_pack(hosted, catalog=catalog, question=record["question"])
        request = build_generation_request(
            question=record["question"],
            schema_pack=pack,
            model_name=hosted.model.model_name,
            temperature=hosted.model.temperature,
            max_output_tokens=hosted.model.max_output_tokens,
            reasoning_effort=hosted.model.reasoning_effort,
        )
        save_record(
            recording,
            hosted.recording_path,
            task_id=task_id,
            digest=request_sha256(task_id, request),
            response=GenerationResponse(
                raw_output=record["SQL"],
                model_name="gpt-5.6-luna",
                requested_model_name="gpt-5.6-luna",
                provider="openai",
                endpoint="responses",
                status="completed",
            ),
        )

    traces, summary = run_hosted_smoke(hosted, replay_only=True)

    assert summary.correct == 2
    assert all(trace.schema_evidence for trace in traces)
    assert all(trace.schema_pack and trace.schema_pack.retrieval_hits for trace in traces)
