import hashlib
import json
from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    GenerationRecording,
    PairedRunComparison,
    RunSummary,
    SchemaEvidenceReport,
)
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]
B2_RESULTS = ROOT / "results" / "b2-openai-gpt-5-6-luna-smoke"
B2_RECORDING = ROOT / "data" / "processed" / "predictions" / "b2-openai-gpt-5-6-luna-smoke.json"
EVIDENCE_ROOT = ROOT / "results" / "schema-evidence-smoke"


def test_committed_b2_artifact_is_complete_and_consistent() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b2-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(B2_RECORDING.read_text(encoding="utf-8"))
    trace_path = B2_RESULTS / "trace.jsonl"
    traces = [
        AuditTrace.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (B2_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(
        (EVIDENCE_ROOT / "b2.json").read_text(encoding="utf-8")
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B2"
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
    assert all(
        trace.schema_pack and len(trace.schema_pack.retrieval_hits) == 12 for trace in traces
    )
    assert all(
        [hit.rank for hit in trace.schema_pack.retrieval_hits] == list(range(1, 13))
        for trace in traces
        if trace.schema_pack
    )
    assert all(trace.schema_evidence for trace in traces)
    assert {trace.software_revision for trace in traces} == {
        "719d6a812cd37c7e6d4e504f3c09c5b0d977be9e"
    }
    encoded_config = json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    configuration_sha256 = hashlib.sha256(encoded_config).hexdigest()
    assert {trace.configuration_sha256 for trace in traces} == {configuration_sha256}
    assert evidence.configuration_sha256 == configuration_sha256
    assert evidence.source_trace_sha256 == hashlib.sha256(trace_path.read_bytes()).hexdigest()

    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {
        "correct": 2,
        "semantic_mismatch": 6,
        "safe_abstention": 10,
        "validator_rejection": 2,
    }
    assert summary.model_dump(exclude={"run_id", "method_id"}) == {
        "tasks": 20,
        "correct": 2,
        "abstained": 10,
        "invalid": 2,
        "execution_errors": 0,
        "input_tokens": 6102,
        "output_tokens": 906,
        "estimated_cost_usd": 0.011538,
    }
    assert evidence.aggregate.tasks_with_full_table_recall == 10
    assert evidence.aggregate.tasks_with_full_column_recall == 8
    assert evidence.aggregate.retrieval_misses == 12


def test_b2_paired_comparisons_include_evidence() -> None:
    b0 = PairedRunComparison.model_validate_json(
        (ROOT / "results" / "b0-vs-b2-openai-gpt-5-6-luna-smoke" / "comparison.json").read_text(
            encoding="utf-8"
        )
    )
    b1 = PairedRunComparison.model_validate_json(
        (ROOT / "results" / "b1-vs-b2-openai-gpt-5-6-luna-smoke" / "comparison.json").read_text(
            encoding="utf-8"
        )
    )

    assert b0.baseline.method_id == "B0" and b0.treatment.method_id == "B2"
    assert b1.baseline.method_id == "B1" and b1.treatment.method_id == "B2"
    assert b0.baseline.schema_evidence and b0.treatment.schema_evidence
    assert b1.baseline.schema_evidence and b1.treatment.schema_evidence
    assert b0.improved_task_ids == ["414"]
    assert b0.regressed_task_ids == ["1042", "24", "47", "740", "800"]
    assert b1.improved_task_ids == ["1351", "414"]
    assert b1.regressed_task_ids == ["1042", "24", "740", "800"]
