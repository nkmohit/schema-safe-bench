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
B3_RESULTS = ROOT / "results" / "b3-openai-gpt-5-6-luna-smoke"
B3_RECORDING = ROOT / "data" / "processed" / "predictions" / "b3-openai-gpt-5-6-luna-smoke.json"
EVIDENCE_ROOT = ROOT / "results" / "schema-evidence-smoke"


def test_committed_b3_artifact_is_complete_and_consistent() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b3-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(B3_RECORDING.read_text(encoding="utf-8"))
    trace_path = B3_RESULTS / "trace.jsonl"
    traces = [
        AuditTrace.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (B3_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(
        (EVIDENCE_ROOT / "b3.json").read_text(encoding="utf-8")
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B3"
    assert config.schema_context and config.schema_context.strategy == "dense"
    assert config.schema_context.embedding
    assert config.schema_context.embedding.revision == ("5c38ec7c405ec4b44b94cc5a9bb96e735b38267a")
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
    assert all(
        [(-hit.score, hit.document_id) for hit in trace.schema_pack.retrieval_hits]
        == sorted((-hit.score, hit.document_id) for hit in trace.schema_pack.retrieval_hits)
        for trace in traces
        if trace.schema_pack
    )
    metadata = [
        trace.schema_pack.retrieval_metadata
        for trace in traces
        if trace.schema_pack and trace.schema_pack.retrieval_metadata
    ]
    assert len(metadata) == 20
    assert {item.policy_id for item in metadata} == {"bge-dense-schema-documents-v1"}
    assert {item.embedding_model_id for item in metadata} == {"BAAI/bge-small-en-v1.5"}
    assert {item.embedding_model_revision for item in metadata} == {
        "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    }
    assert {item.embedding_dimension for item in metadata} == {384}
    assert {item.device for item in metadata} == {"cpu"}
    assert {item.precision for item in metadata} == {"float32"}
    assert {item.embedding_library_version for item in metadata} == {"3.4.1"}
    assert all(len(item.document_embeddings_sha256) == 64 for item in metadata)
    assert all(len(item.query_embedding_sha256) == 64 for item in metadata)
    assert all(trace.schema_evidence for trace in traces)
    assert {trace.software_revision for trace in traces} == {
        "59677d0d897198b10cf728d49e7a45a7c88173b3"
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
        "correct": 3,
        "semantic_mismatch": 7,
        "safe_abstention": 9,
        "validator_rejection": 1,
    }
    assert summary.model_dump(exclude={"run_id", "method_id"}) == {
        "tasks": 20,
        "correct": 3,
        "abstained": 9,
        "invalid": 1,
        "execution_errors": 0,
        "input_tokens": 6695,
        "output_tokens": 767,
        "estimated_cost_usd": 0.011297,
    }
    assert evidence.aggregate.tasks_with_full_table_recall == 13
    assert evidence.aggregate.tasks_with_full_column_recall == 9
    assert evidence.aggregate.retrieval_misses == 11


def test_b3_paired_comparisons_include_evidence() -> None:
    comparisons = {
        baseline: PairedRunComparison.model_validate_json(
            (
                ROOT
                / "results"
                / f"{baseline.lower()}-vs-b3-openai-gpt-5-6-luna-smoke"
                / "comparison.json"
            ).read_text(encoding="utf-8")
        )
        for baseline in ("B0", "B1", "B2")
    }

    assert all(item.treatment.method_id == "B3" for item in comparisons.values())
    assert all(item.baseline.method_id == name for name, item in comparisons.items())
    assert all(item.baseline.schema_evidence for item in comparisons.values())
    assert all(item.treatment.schema_evidence for item in comparisons.values())
    assert comparisons["B0"].improved_task_ids == ["414"]
    assert comparisons["B0"].regressed_task_ids == ["24", "47", "740", "800"]
    assert comparisons["B1"].improved_task_ids == ["1351", "414"]
    assert comparisons["B1"].regressed_task_ids == ["24", "740", "800"]
    assert comparisons["B2"].improved_task_ids == ["1042"]
    assert comparisons["B2"].regressed_task_ids == []
