import hashlib
import json
from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    PairedRunComparison,
    RepairRecording,
    RunSummary,
    SchemaEvidenceReport,
)
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]
B4_RESULTS = ROOT / "results" / "b4-openai-gpt-5-6-luna-smoke"
B6_RESULTS = ROOT / "results" / "b6-openai-gpt-5-6-luna-smoke"
B6_RECORDING = ROOT / "data/processed/predictions/b6-openai-gpt-5-6-luna-repair-smoke.json"
EVIDENCE = ROOT / "results/schema-evidence-smoke/b6.json"
IMPLEMENTATION_REVISION = "52c1232c6b86413f8ea7d7b7daad4246aba70c7f"


def _traces(path: Path) -> list[AuditTrace]:
    return [AuditTrace.model_validate_json(line) for line in path.read_text().splitlines()]


def test_committed_b6_artifact_is_complete_consistent_and_bounded() -> None:
    config = load_hosted_run_config(ROOT / "configs/runs/b6-openai-luna-smoke.yaml")
    trace_path = B6_RESULTS / "trace.jsonl"
    traces = _traces(trace_path)
    b4 = {trace.task_id: trace for trace in _traces(B4_RESULTS / "trace.jsonl")}
    summary = RunSummary.model_validate_json(
        (B6_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(EVIDENCE.read_text(encoding="utf-8"))
    recording = RepairRecording.model_validate_json(B6_RECORDING.read_text(encoding="utf-8"))
    provenance = json.loads(
        (ROOT / "data/provenance/b6-validator-repair.json").read_text(encoding="utf-8")
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B6"
    assert len(traces) == summary.tasks == 20
    assert {trace.software_revision for trace in traces} == {IMPLEMENTATION_REVISION}
    assert {record.task_id for record in recording.records} == {"116", "1185"}
    assert {record.stage for record in recording.records} == {"repair-1"}
    eligible = [trace for trace in traces if trace.repair and trace.repair.eligible]
    assert {trace.task_id for trace in eligible} == {"116", "1185"}
    assert all(trace.repair_count == 1 for trace in eligible)
    assert all(trace.repair and trace.repair.attempted for trace in eligible)
    assert all(trace.repair_count == 0 for trace in traces if trace not in eligible)
    assert all(
        trace.repair and not trace.repair.attempted for trace in traces if trace not in eligible
    )

    for trace in traces:
        first = b4[trace.task_id]
        assert trace.schema_pack == first.schema_pack
        assert trace.repair
        assert trace.repair.first_pass_request_sha256 == first.request_sha256
        assert trace.repair.first_pass_candidate_sql == first.candidate_sql
        assert trace.repair.first_pass_generation.model_dump(exclude={"replayed"}) == (
            first.generation.model_dump(exclude={"replayed"})
        )

    repaired = {trace.task_id: trace for trace in eligible}
    assert repaired["116"].repair.cause.normalized_error == "execution:query_budget_exceeded"
    assert repaired["116"].failure_label == "validator_rejection"
    assert repaired["1185"].repair.cause.trigger == "validation"
    assert repaired["1185"].failure_label == "safe_abstention"

    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {
        "correct": 3,
        "semantic_mismatch": 9,
        "safe_abstention": 7,
        "validator_rejection": 1,
    }
    assert summary.repair_accounting
    assert summary.repair_accounting.eligible == summary.repair_accounting.attempted == 2
    assert summary.repair_accounting.first_pass.estimated_cost_usd == 0.01309
    assert summary.repair_accounting.incremental_repair.estimated_cost_usd == 0.001678
    assert summary.repair_accounting.total.estimated_cost_usd == 0.014768
    assert summary.estimated_cost_usd == 0.014768

    encoded_config = json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    configuration_sha256 = hashlib.sha256(encoded_config).hexdigest()
    assert {trace.configuration_sha256 for trace in traces} == {configuration_sha256}
    assert evidence.configuration_sha256 == configuration_sha256
    assert evidence.source_trace_sha256 == hashlib.sha256(trace_path.read_bytes()).hexdigest()
    published = provenance["published_result"]
    assert (
        published["repair_recording_sha256"]
        == hashlib.sha256(B6_RECORDING.read_bytes()).hexdigest()
    )
    assert published["trace_sha256"] == hashlib.sha256(trace_path.read_bytes()).hexdigest()
    assert evidence.aggregate.tasks_with_full_table_recall == 14
    assert evidence.aggregate.tasks_with_full_column_recall == 10
    assert evidence.aggregate.retrieval_misses == 10


def test_b6_paired_comparisons_preserve_exact_transitions_and_total_cost() -> None:
    b4 = PairedRunComparison.model_validate_json(
        (ROOT / "results/b4-vs-b6-openai-gpt-5-6-luna-smoke/comparison.json").read_text()
    )
    b0 = PairedRunComparison.model_validate_json(
        (ROOT / "results/b0-vs-b6-openai-gpt-5-6-luna-smoke/comparison.json").read_text()
    )
    assert b4.treatment.method_id == b0.treatment.method_id == "B6"
    assert b4.improved_task_ids == b4.regressed_task_ids == []
    assert b4.deltas["estimated_cost_usd"] == 0.001678
    assert b4.treatment.estimated_cost_usd == 0.014768
    changed = {
        item.task_id: (item.baseline_outcome, item.treatment_outcome)
        for item in b4.paired_outcomes
        if item.baseline_outcome != item.treatment_outcome
    }
    assert changed == {
        "116": ("execution_failure", "validator_rejection"),
        "1185": ("validator_rejection", "safe_abstention"),
    }
    assert b0.regressed_task_ids == ["24", "47", "740"]
