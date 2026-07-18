import hashlib
import json
from collections import Counter
from pathlib import Path

from schema_safe_bench.models import (
    AuditTrace,
    PairedRunComparison,
    RunSummary,
    SchemaEvidenceReport,
)
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]
B4_RESULTS = ROOT / "results/b4-openai-gpt-5-6-luna-smoke"
B7_RESULTS = ROOT / "results/b7-openai-gpt-5-6-luna-smoke"
B7_EVIDENCE = ROOT / "results/schema-evidence-smoke/b7.json"
IMPLEMENTATION_REVISION = "9061bf3e77d8cf9239fed2f76298f41e963c767a"


def _traces(path: Path) -> list[AuditTrace]:
    return [AuditTrace.model_validate_json(line) for line in path.read_text().splitlines()]


def test_committed_b7_artifact_is_complete_consistent_and_call_free() -> None:
    config = load_hosted_run_config(ROOT / "configs/runs/b7-openai-luna-smoke.yaml")
    trace_path = B7_RESULTS / "trace.jsonl"
    traces = _traces(trace_path)
    b4 = {trace.task_id: trace for trace in _traces(B4_RESULTS / "trace.jsonl")}
    summary = RunSummary.model_validate_json(
        (B7_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(B7_EVIDENCE.read_text(encoding="utf-8"))
    provenance = json.loads(
        (ROOT / "data/provenance/b7-validator-abstention.json").read_text(encoding="utf-8")
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B7"
    assert len(traces) == summary.tasks == 20
    assert {trace.software_revision for trace in traces} == {IMPLEMENTATION_REVISION}
    assert all(trace.abstention for trace in traces)
    enforced = [trace for trace in traces if trace.abstention and trace.abstention.enforced]
    model_abstentions = [
        trace
        for trace in traces
        if trace.abstention and trace.abstention.decision == "model_abstention"
    ]
    assert {trace.task_id for trace in enforced} == {"116", "1185"}
    assert {trace.task_id for trace in model_abstentions} == {
        "24",
        "1155",
        "740",
        "898",
        "1464",
        "637",
    }
    assert all(trace.candidate_sql == "ABSTAIN" for trace in enforced)
    assert all(trace.repair is None and trace.repair_count == 0 for trace in traces)

    for trace in traces:
        first = b4[trace.task_id]
        assert trace.schema_pack == first.schema_pack
        assert trace.request_sha256 == first.request_sha256
        assert trace.generation == first.generation
        assert trace.abstention
        assert trace.abstention.first_pass_candidate_sql == first.candidate_sql
        assert trace.abstention.first_pass_request_sha256 == first.request_sha256
        assert trace.abstention.first_pass_generation == first.generation

    decisions = Counter(trace.abstention.decision for trace in traces if trace.abstention)
    assert decisions == {"query": 12, "model_abstention": 6, "enforced_abstention": 2}
    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {"correct": 3, "semantic_mismatch": 9, "safe_abstention": 8}
    assert summary.abstention_accounting
    accounting = summary.abstention_accounting
    assert accounting.model_abstentions == 6
    assert accounting.enforced_abstentions == 2
    assert accounting.coverage == 0.4
    assert accounting.unsafe_terminal_avoidance_rate == 1.0
    assert accounting.incremental.requests == 0
    assert accounting.incremental.estimated_cost_usd == 0
    assert accounting.first_pass == accounting.total
    assert summary.estimated_cost_usd == 0.01309

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
    assert published["trace_sha256"] == hashlib.sha256(trace_path.read_bytes()).hexdigest()
    assert (
        published["summary_sha256"]
        == hashlib.sha256((B7_RESULTS / "trace.summary.json").read_bytes()).hexdigest()
    )
    assert evidence.aggregate.tasks_with_full_table_recall == 14
    assert evidence.aggregate.tasks_with_full_column_recall == 10
    assert evidence.aggregate.retrieval_misses == 10


def test_b7_paired_comparisons_preserve_exact_transitions_and_zero_increment() -> None:
    b4 = PairedRunComparison.model_validate_json(
        (ROOT / "results/b4-vs-b7-openai-gpt-5-6-luna-smoke/comparison.json").read_text()
    )
    b0 = PairedRunComparison.model_validate_json(
        (ROOT / "results/b0-vs-b7-openai-gpt-5-6-luna-smoke/comparison.json").read_text()
    )
    assert b4.treatment.method_id == b0.treatment.method_id == "B7"
    assert b4.improved_task_ids == b4.regressed_task_ids == []
    assert b4.deltas["estimated_cost_usd"] == 0
    assert b4.deltas["input_tokens"] == b4.deltas["output_tokens"] == 0
    changed = {
        item.task_id: (item.baseline_outcome, item.treatment_outcome)
        for item in b4.paired_outcomes
        if item.baseline_outcome != item.treatment_outcome
    }
    assert changed == {
        "116": ("execution_failure", "safe_abstention"),
        "1185": ("validator_rejection", "safe_abstention"),
    }
    assert b0.regressed_task_ids == ["24", "47", "740"]
