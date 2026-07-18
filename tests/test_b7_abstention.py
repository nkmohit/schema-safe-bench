from pathlib import Path

import pytest

from schema_safe_bench.generation import request_sha256
from schema_safe_bench.models import (
    AbstentionPolicyConfig,
    AuditTrace,
    BenchmarkTask,
    ExecutionResult,
    HostedRunConfig,
    ValidationIssue,
    ValidationResult,
)
from schema_safe_bench.prompting import build_generation_request
from schema_safe_bench.runner import (
    _abstention_cause,
    load_hosted_run_config,
    run_hosted_smoke,
)

ROOT = Path(__file__).resolve().parents[1]
B7_CONFIG = ROOT / "configs/runs/b7-openai-luna-smoke.yaml"


def test_b7_config_locks_b4_and_deterministic_abstention() -> None:
    config = load_hosted_run_config(B7_CONFIG)
    assert config.method_id == "B7"
    assert isinstance(config.reliability, AbstentionPolicyConfig)
    assert config.recording_path == config.reliability.first_pass_recording_path
    assert config.schema_context and config.schema_context.strategy == "hybrid"
    assert config.schema_context.lexical_weight == 1.0
    assert config.schema_context.dense_weight == 1.0
    assert config.reliability.policy_id == "validator-controlled-execution-abstention-v1"


def test_abstention_enforcement_is_limited_to_unsafe_terminal_states() -> None:
    invalid = ValidationResult(
        status="invalid",
        issues=[ValidationIssue(code="unknown_column", message="raw", identifier="missing")],
    )
    cause = _abstention_cause(invalid, ExecutionResult(status="rejected"))
    assert cause and cause.normalized_error == "validation:unknown_column(missing)"

    valid = ValidationResult(status="valid", normalized_sql="SELECT 1")
    cause = _abstention_cause(
        valid,
        ExecutionResult(status="interrupted", error_type="query_budget_exceeded"),
    )
    assert cause and cause.normalized_error == "execution:query_budget_exceeded"
    assert _abstention_cause(valid, ExecutionResult(status="success")) is None
    assert (
        _abstention_cause(
            ValidationResult(status="abstain"),
            ExecutionResult(status="rejected", error_type="validation_required"),
        )
        is None
    )


def test_evaluator_only_mutation_cannot_change_abstention_decision() -> None:
    public = BenchmarkTask(
        task_id="task",
        db_id="db",
        question="Question",
        reference_sql="SELECT 1",
        evidence="public evaluator evidence",
    )
    mutated = public.model_copy(
        update={"reference_sql": "SELECT secret", "evidence": "mutated evaluator evidence"}
    )
    validation = ValidationResult(
        status="invalid",
        issues=[ValidationIssue(code="unknown_table", message="raw", identifier="invented")],
    )
    execution = ExecutionResult(status="rejected")
    decision_before = _abstention_cause(validation, execution)
    assert public.question == mutated.question
    assert public.reference_sql != mutated.reference_sql
    assert public.evidence != mutated.evidence
    decision_after = _abstention_cause(validation, execution)
    assert decision_before == decision_after

    first = AuditTrace.model_validate_json(
        next(
            line
            for line in (ROOT / "results/b4-openai-gpt-5-6-luna-smoke/trace.jsonl")
            .read_text()
            .splitlines()
            if '"task_id":"116"' in line
        )
    )
    assert first.schema_pack
    before_request = build_generation_request(
        question=public.question,
        schema_pack=first.schema_pack,
        model_name="gpt-5.6-luna",
    )
    after_request = build_generation_request(
        question=mutated.question,
        schema_pack=first.schema_pack,
        model_name="gpt-5.6-luna",
    )
    assert request_sha256(public.task_id, before_request) == request_sha256(
        mutated.task_id, after_request
    )


def test_b7_real_b4_inputs_freeze_exact_abstention_decisions(tmp_path: Path) -> None:
    config = load_hosted_run_config(B7_CONFIG).model_copy(
        update={"output_path": tmp_path / "trace.jsonl"}
    )
    traces, summary = run_hosted_smoke(config, replay_only=True)
    enforced = [trace for trace in traces if trace.abstention and trace.abstention.enforced]
    model_abstentions = [
        trace
        for trace in traces
        if trace.abstention and trace.abstention.decision == "model_abstention"
    ]
    assert {trace.task_id for trace in enforced} == {"116", "1185"}
    assert len(model_abstentions) == 6
    assert all(trace.candidate_sql == "ABSTAIN" for trace in enforced)
    assert summary.abstention_accounting
    assert summary.abstention_accounting.enforced_abstentions == 2
    assert summary.abstention_accounting.model_abstentions == 6
    assert summary.abstention_accounting.incremental.requests == 0
    assert summary.abstention_accounting.incremental.estimated_cost_usd == 0


def test_b7_rejects_first_pass_configuration_drift(tmp_path: Path) -> None:
    config = load_hosted_run_config(B7_CONFIG)
    assert isinstance(config.reliability, AbstentionPolicyConfig)
    drifted = config.model_copy(
        update={
            "output_path": tmp_path / "trace.jsonl",
            "model": config.model.model_copy(update={"max_output_tokens": 999}),
        }
    )
    with pytest.raises(ValueError, match="B7 model must exactly match"):
        run_hosted_smoke(drifted, replay_only=True)


def test_b7_fails_closed_when_first_pass_trace_is_missing(tmp_path: Path) -> None:
    config = load_hosted_run_config(B7_CONFIG)
    assert isinstance(config.reliability, AbstentionPolicyConfig)
    missing = config.reliability.model_copy(
        update={"first_pass_trace_path": tmp_path / "missing.jsonl"}
    )
    config = config.model_copy(
        update={"output_path": tmp_path / "trace.jsonl", "reliability": missing}
    )
    with pytest.raises(FileNotFoundError):
        run_hosted_smoke(config, replay_only=True)


def test_non_b7_method_rejects_abstention_policy() -> None:
    b7 = load_hosted_run_config(B7_CONFIG)
    payload = b7.model_dump(by_alias=True)
    payload["method_id"] = "B4"
    with pytest.raises(ValueError, match="only B6 or B7"):
        HostedRunConfig.model_validate(payload)
