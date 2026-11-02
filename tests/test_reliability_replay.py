"""B6 repair and B7 abstention replay without the BIRD databases or a hosted model."""

import json
from pathlib import Path

import pytest
import yaml
from test_runner import _b4_hosted, _FakeDenseEmbedder, _run_inputs

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.generation import (
    load_recording,
    load_repair_recording,
    repair_request_sha256,
    request_sha256,
    save_record,
    save_repair_record,
)
from schema_safe_bench.models import GenerationRequest, GenerationResponse, HostedRunConfig
from schema_safe_bench.prompting import build_generation_request
from schema_safe_bench.runner import _hosted_schema_pack, load_hosted_run_config, run_hosted_smoke


def _completed(raw_output: str) -> GenerationResponse:
    return GenerationResponse(
        raw_output=raw_output,
        model_name="gpt-5.6-luna",
        requested_model_name="gpt-5.6-luna",
        provider="openai",
        endpoint="responses",
        status="completed",
    )


def test_b6_and_b7_replay_on_a_tiny_database(
    sample_database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _run_inputs(sample_database, tmp_path)
    tasks = [
        {
            "question_id": 1,
            "db_id": "shop",
            "question": "List customer names",
            "SQL": "SELECT name FROM customers ORDER BY name",
        },
        {
            "question_id": 2,
            "db_id": "shop",
            "question": "Refer to a missing column",
            "SQL": "SELECT name FROM customers",
        },
        {
            "question_id": 3,
            "db_id": "shop",
            "question": "This cannot be answered from the schema",
            "SQL": "SELECT name FROM customers",
        },
    ]
    base.tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
    manifest = json.loads(base.manifest_path.read_text(encoding="utf-8"))
    manifest["task_ids"] = ["1", "2", "3"]
    base.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    b4 = _b4_hosted(base, tmp_path)
    config_path = tmp_path / "b4.yaml"
    config_path.write_text(
        yaml.safe_dump(b4.model_dump(mode="json", by_alias=True)),
        encoding="utf-8",
    )
    b4 = load_hosted_run_config(config_path)
    monkeypatch.setattr(
        "schema_safe_bench.runner.SentenceTransformerEmbedder",
        lambda _config: _FakeDenseEmbedder(),
    )
    catalog = extract_catalog(base.databases_root / "shop" / "shop.sqlite", db_id="shop")
    outputs = {
        "1": "SELECT name FROM customers ORDER BY name",
        "2": "SELECT missing_column FROM customers",
        "3": "ABSTAIN",
    }
    recording = load_recording(b4.recording_path, model_name=b4.model.model_name)
    for task in tasks:
        task_id = str(task["question_id"])
        pack = _hosted_schema_pack(
            b4,
            catalog=catalog,
            question=task["question"],
            dense_embedder=_FakeDenseEmbedder(),
            dense_retrievers={},
        )
        request = build_generation_request(
            question=task["question"],
            schema_pack=pack,
            model_name=b4.model.model_name,
            temperature=b4.model.temperature,
            max_output_tokens=b4.model.max_output_tokens,
            reasoning_effort=b4.model.reasoning_effort,
        )
        save_record(
            recording,
            b4.recording_path,
            task_id=task_id,
            digest=request_sha256(task_id, request),
            response=_completed(outputs[task_id]),
        )

    first_traces, _summary = run_hosted_smoke(b4, replay_only=True)
    b4.output_path.parent.mkdir(parents=True, exist_ok=True)
    b4.output_path.write_text(
        "".join(trace.model_dump_json() + "\n" for trace in first_traces),
        encoding="utf-8",
    )
    repair_path = tmp_path / "repairs.json"
    b4_payload = b4.model_dump(mode="json", by_alias=True)
    b6 = HostedRunConfig.model_validate(
        {
            **b4_payload,
            "run_id": "b6-fixture",
            "method_id": "B6",
            "output_path": str(tmp_path / "b6" / "trace.jsonl"),
            "reliability": {
                "validate": True,
                "max_repairs": 1,
                "allow_abstain": True,
                "first_pass_method_id": "B4",
                "first_pass_config_path": str(config_path),
                "first_pass_recording_path": str(b4.recording_path),
                "first_pass_trace_path": str(b4.output_path),
                "repair_recording_path": str(repair_path),
            },
        }
    )
    captured: list[GenerationRequest] = []

    def reserve(request: GenerationRequest) -> int:
        captured.append(request)
        return 1

    monkeypatch.setattr("schema_safe_bench.runner.maximum_request_cost", reserve)
    with pytest.raises(RuntimeError, match="missing recorded repair responses"):
        run_hosted_smoke(b6, replay_only=True)
    assert len(captured) == 1
    assert "missing column" in captured[0].messages[-1].content

    repair_recording = load_repair_recording(repair_path, model_name=b4.model.model_name)
    save_repair_record(
        repair_recording,
        repair_path,
        task_id="2",
        stage="repair-1",
        digest=repair_request_sha256("2", "repair-1", captured[0]),
        response=_completed("SELECT name FROM customers"),
    )
    repaired, repair_summary = run_hosted_smoke(b6, replay_only=True)
    attempted = [trace for trace in repaired if trace.repair and trace.repair.attempted]
    assert {trace.task_id for trace in attempted} == {"2"}
    assert attempted[0].candidate_sql == "SELECT name FROM customers"
    assert repair_summary.repair_accounting is not None
    assert repair_summary.repair_accounting.eligible == 1
    assert repair_summary.repair_accounting.attempted == 1
    assert repair_summary.repair_accounting.incremental_repair.requests == 1

    b7 = HostedRunConfig.model_validate(
        {
            **b4_payload,
            "run_id": "b7-fixture",
            "method_id": "B7",
            "output_path": str(tmp_path / "b7" / "trace.jsonl"),
            "reliability": {
                "validate": True,
                "allow_model_abstain": True,
                "policy_id": "validator-controlled-execution-abstention-v1",
                "first_pass_method_id": "B4",
                "first_pass_config_path": str(config_path),
                "first_pass_recording_path": str(b4.recording_path),
                "first_pass_trace_path": str(b4.output_path),
            },
        }
    )
    abstained, abstention_summary = run_hosted_smoke(b7, replay_only=True)
    decisions = {
        trace.task_id: trace.abstention.decision for trace in abstained if trace.abstention
    }
    assert decisions == {"1": "query", "2": "enforced_abstention", "3": "model_abstention"}
    assert abstained[1].candidate_sql == "ABSTAIN"
    assert abstention_summary.abstention_accounting is not None
    assert abstention_summary.abstention_accounting.enforced_abstentions == 1
    assert abstention_summary.abstention_accounting.model_abstentions == 1
    assert abstention_summary.abstention_accounting.incremental.requests == 0
