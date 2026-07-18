from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    GenerationRecording,
    RunSummary,
)
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "b0-openai-gpt-5-6-luna-smoke"
RECORDING = ROOT / "data" / "processed" / "predictions" / "b0-openai-gpt-5-6-luna-smoke.json"


def test_committed_hosted_smoke_artifact_is_internally_consistent() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b0-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(RECORDING.read_text(encoding="utf-8"))
    traces = [
        AuditTrace.model_validate_json(line)
        for line in (RESULTS / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )

    assert config.model.model_name == "gpt-5.6-luna"
    assert config.model.temperature == 0.0
    assert config.model.reasoning_effort == "none"
    assert config.model.max_output_tokens == 1000
    assert config.model.store is False
    assert config.budget.project_limit_usd < 100
    assert len(recording.records) == len(traces) == summary.tasks == 20
    assert {record.task_id for record in recording.records} == {trace.task_id for trace in traces}
    assert {record.request_sha256 for record in recording.records} == {
        trace.request_sha256 for trace in traces
    }
    assert all(trace.generation for trace in traces)
    assert {trace.generation.requested_model_name for trace in traces if trace.generation} == {
        "gpt-5.6-luna"
    }
    assert {trace.generation.model_name for trace in traces if trace.generation} == {"gpt-5.6-luna"}
    assert {trace.generation.status for trace in traces if trace.generation} == {"completed"}
    assert not any(trace.generation.replayed for trace in traces if trace.generation)
    assert {trace.comparison.policy for trace in traces if trace.comparison} == {
        "bird-execution-v1"
    }
    assert len({trace.configuration_sha256 for trace in traces}) == 1
    assert {trace.software_revision for trace in traces} == {
        "d9d89a025058c4561e41cca0a711c9082048b05e"
    }

    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {
        "correct": 6,
        "semantic_mismatch": 10,
        "safe_abstention": 2,
        "execution_failure": 2,
    }
    assert summary.correct == 6
    assert summary.input_tokens == sum(
        trace.generation.input_tokens or 0 for trace in traces if trace.generation
    )
    assert summary.output_tokens == sum(
        trace.generation.output_tokens or 0 for trace in traces if trace.generation
    )
    assert summary.estimated_cost_usd == round(
        sum(trace.generation.estimated_cost_usd or 0.0 for trace in traces if trace.generation),
        8,
    )
    assert summary.estimated_cost_usd == 0.019454
