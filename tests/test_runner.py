import json
from pathlib import Path

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
from schema_safe_bench.retrieval import full_schema_pack, length_truncated_schema_pack
from schema_safe_bench.runner import (
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
