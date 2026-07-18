import hashlib
import json
from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    GenerationRecording,
    PairedRunComparison,
    RunSummary,
)
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]
B1_RESULTS = ROOT / "results" / "b1-openai-gpt-5-6-luna-smoke"
B1_RECORDING = ROOT / "data" / "processed" / "predictions" / "b1-openai-gpt-5-6-luna-smoke.json"
COMPARISON = ROOT / "results" / "b0-vs-b1-openai-gpt-5-6-luna-smoke" / "comparison.json"


def test_committed_b1_artifact_and_paired_comparison_are_consistent() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b1-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(B1_RECORDING.read_text(encoding="utf-8"))
    traces = [
        AuditTrace.model_validate_json(line)
        for line in (B1_RESULTS / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (B1_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    comparison = PairedRunComparison.model_validate_json(COMPARISON.read_text(encoding="utf-8"))

    assert config.method_id == summary.method_id == "B1"
    assert config.schema_context is not None
    assert config.schema_context.policy_id == "catalog-character-prefix-v1"
    assert config.schema_context.max_chars == 1000
    assert len(recording.records) == len(traces) == summary.tasks == 20
    assert {record.task_id for record in recording.records} == {trace.task_id for trace in traces}
    assert {record.request_sha256 for record in recording.records} == {
        trace.request_sha256 for trace in traces
    }
    assert {trace.generation.requested_model_name for trace in traces if trace.generation} == {
        "gpt-5.6-luna"
    }
    assert {trace.generation.model_name for trace in traces if trace.generation} == {"gpt-5.6-luna"}
    assert {trace.generation.status for trace in traces if trace.generation} == {"completed"}
    assert not any(trace.generation.replayed for trace in traces if trace.generation)
    assert all(trace.schema_pack for trace in traces)
    assert max(len(trace.schema_pack.serialized) for trace in traces if trace.schema_pack) <= 1000
    assert all(
        column.name in trace.schema_pack.serialized
        for trace in traces
        if trace.schema_pack
        for table in trace.schema_pack.tables
        for column in table.columns
    )
    assert {trace.comparison.policy for trace in traces if trace.comparison} == {
        "bird-execution-v1"
    }
    encoded_config = json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert {trace.configuration_sha256 for trace in traces} == {
        hashlib.sha256(encoded_config).hexdigest()
    }
    assert {trace.software_revision for trace in traces} == {
        "12d81ff81573ebf60a5f43078b2a687e51943839"
    }

    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {
        "correct": 4,
        "semantic_mismatch": 7,
        "safe_abstention": 6,
        "validator_rejection": 3,
    }
    assert summary.model_dump(exclude={"run_id", "method_id"}) == {
        "tasks": 20,
        "correct": 4,
        "abstained": 6,
        "invalid": 3,
        "execution_errors": 0,
        "input_tokens": 6381,
        "output_tokens": 1169,
        "estimated_cost_usd": 0.013395,
    }
    assert comparison.baseline.method_id == "B0"
    assert comparison.treatment.method_id == "B1"
    assert comparison.context_truncated_tasks == 15
    assert comparison.improved_task_ids == []
    assert comparison.regressed_task_ids == ["1351", "47"]
    assert comparison.deltas == {
        "correct": -2,
        "accuracy": -0.1,
        "abstained": 4,
        "invalid": 3,
        "execution_errors": -2,
        "schema_chars": -20877,
        "input_tokens": -5207,
        "output_tokens": -142,
        "estimated_cost_usd": -0.006059,
    }
