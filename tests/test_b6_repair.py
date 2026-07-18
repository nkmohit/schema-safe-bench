from pathlib import Path

import pytest

import schema_safe_bench.runner as runner
from schema_safe_bench.generation import (
    load_repair_recording,
    recorded_repair_response,
    repair_request_sha256,
    save_repair_record,
)
from schema_safe_bench.models import (
    ExecutionResult,
    GenerationRequest,
    GenerationResponse,
    PromptMessage,
    ValidationIssue,
    ValidationResult,
)
from schema_safe_bench.runner import _repair_cause, load_hosted_run_config, run_hosted_smoke

ROOT = Path(__file__).resolve().parents[1]
B6_CONFIG = ROOT / "configs/runs/b6-openai-luna-smoke.yaml"


def test_b6_config_locks_b4_and_one_bounded_repair() -> None:
    config = load_hosted_run_config(B6_CONFIG)
    assert config.method_id == "B6"
    assert config.recording_path == config.reliability.first_pass_recording_path
    assert config.schema_context.strategy == "hybrid"
    assert config.schema_context.lexical_weight == 1.0
    assert config.schema_context.dense_weight == 1.0
    assert config.reliability.max_repairs == 1
    assert config.reliability.eligibility_policy == "validator-or-controlled-execution-v1"


def test_repair_eligibility_excludes_abstention_and_semantic_success() -> None:
    abstain = ValidationResult(status="abstain")
    rejected = ExecutionResult(status="rejected", error_type="validation_required")
    assert _repair_cause(abstain, rejected) is None

    valid = ValidationResult(status="valid", normalized_sql="SELECT 1")
    success = ExecutionResult(status="success")
    assert _repair_cause(valid, success) is None


def test_repair_eligibility_normalizes_validator_and_executor_errors() -> None:
    invalid = ValidationResult(
        status="invalid",
        issues=[ValidationIssue(code="unknown_column", message="raw", identifier="missing")],
    )
    cause = _repair_cause(invalid, ExecutionResult(status="rejected"))
    assert cause and cause.normalized_error == "validation:unknown_column(missing)"

    valid = ValidationResult(status="valid", normalized_sql="SELECT 1")
    cause = _repair_cause(
        valid,
        ExecutionResult(status="interrupted", error_type="query_budget_exceeded"),
    )
    assert cause and cause.normalized_error == "execution:query_budget_exceeded"


def test_repair_recording_digest_is_stage_bound(tmp_path: Path) -> None:
    request = GenerationRequest(
        messages=[PromptMessage(role="user", content="repair")],
        model_name="gpt-5.6-luna",
        prompt_version="repair-test",
    )
    digest = repair_request_sha256("116", "repair-1", request)
    assert digest != repair_request_sha256("116", "repair-2", request)
    path = tmp_path / "repair.json"
    recording = load_repair_recording(path, model_name="gpt-5.6-luna")
    response = GenerationResponse(
        raw_output="SELECT 1",
        model_name="gpt-5.6-luna",
        requested_model_name="gpt-5.6-luna",
        provider="openai",
        endpoint="responses",
        status="completed",
    )
    save_repair_record(
        recording,
        path,
        task_id="116",
        stage="repair-1",
        digest=digest,
        response=response,
    )
    loaded = load_repair_recording(path, model_name="gpt-5.6-luna")
    replay = recorded_repair_response(
        loaded,
        task_id="116",
        stage="repair-1",
        expected_request_sha256=digest,
    )
    assert replay and replay.replayed


def test_b6_real_first_pass_freezes_two_eligible_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_hosted_run_config(B6_CONFIG)
    assert config.reliability is not None
    config = config.model_copy(
        update={
            "output_path": tmp_path / "trace.jsonl",
            "reliability": config.reliability.model_copy(
                update={"repair_recording_path": tmp_path / "repairs.json"}
            ),
        }
    )
    reservations = []

    def reserve(request: GenerationRequest) -> int:
        reservations.append(request)
        return 1

    monkeypatch.setattr(runner, "maximum_request_cost", reserve)
    with pytest.raises(RuntimeError, match="missing recorded repair responses"):
        run_hosted_smoke(config, replay_only=True)
    assert len(reservations) == 2
