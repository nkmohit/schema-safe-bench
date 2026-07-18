import hashlib
import json
import math
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
B4_RESULTS = ROOT / "results" / "b4-openai-gpt-5-6-luna-smoke"
B4_RECORDING = ROOT / "data" / "processed" / "predictions" / "b4-openai-gpt-5-6-luna-smoke.json"
EVIDENCE_ROOT = ROOT / "results" / "schema-evidence-smoke"


def test_committed_b4_artifact_is_complete_and_consistent() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b4-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(B4_RECORDING.read_text(encoding="utf-8"))
    trace_path = B4_RESULTS / "trace.jsonl"
    traces = [
        AuditTrace.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (B4_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(
        (EVIDENCE_ROOT / "b4.json").read_text(encoding="utf-8")
    )
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b4-hybrid-schema-retrieval.json").read_text(
            encoding="utf-8"
        )
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B4"
    assert config.schema_context and config.schema_context.strategy == "hybrid"
    assert config.schema_context.embedding
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
    hits = [
        hit for trace in traces if trace.schema_pack for hit in trace.schema_pack.retrieval_hits
    ]
    assert len(hits) == 240
    assert all(set(hit.component_scores) == {"bm25", "dense"} for hit in hits)
    assert all(set(hit.component_ranks) == {"bm25", "dense"} for hit in hits)
    assert all(set(hit.component_contributions) == {"bm25", "dense"} for hit in hits)
    assert all(math.isclose(hit.score, sum(hit.component_contributions.values())) for hit in hits)
    metadata = [
        trace.schema_pack.retrieval_metadata
        for trace in traces
        if trace.schema_pack and trace.schema_pack.retrieval_metadata
    ]
    assert len(metadata) == 20
    assert {item.policy_id for item in metadata} == {"bm25-bge-rrf-schema-documents-v1"}
    assert {item.strategy for item in metadata} == {"hybrid"}
    assert {item.fusion_algorithm for item in metadata} == {"weighted-reciprocal-rank-fusion"}
    assert {item.fusion_candidate_depth for item in metadata} == {"all_documents"}
    assert {item.fusion_lexical_weight for item in metadata} == {1.0}
    assert {item.fusion_dense_weight for item in metadata} == {1.0}
    assert {item.fusion_rank_constant for item in metadata} == {60}
    assert {item.embedding_model_revision for item in metadata} == {
        "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    }
    assert all(trace.schema_evidence for trace in traces)
    assert {trace.software_revision for trace in traces} == {
        "1dee8779062d14837f930603bda1b93fde9870fd"
    }
    pack_digest = hashlib.sha256()
    for trace in traces:
        assert trace.schema_pack
        pack_digest.update(trace.schema_pack.model_dump_json().encode())
    assert (
        pack_digest.hexdigest()
        == provenance["pre_generation_pack_audit"]["ordered_schema_packs_sha256"]
    )
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
        "semantic_mismatch": 9,
        "safe_abstention": 6,
        "validator_rejection": 1,
        "execution_failure": 1,
    }
    assert summary.model_dump(exclude={"run_id", "method_id"}) == {
        "tasks": 20,
        "correct": 3,
        "abstained": 6,
        "invalid": 1,
        "execution_errors": 1,
        "input_tokens": 6502,
        "output_tokens": 1098,
        "estimated_cost_usd": 0.01309,
    }
    assert evidence.aggregate.tasks_with_full_table_recall == 14
    assert evidence.aggregate.tasks_with_full_column_recall == 10
    assert evidence.aggregate.retrieval_misses == 10


def test_b4_paired_comparisons_include_evidence() -> None:
    comparisons = {
        baseline: PairedRunComparison.model_validate_json(
            (
                ROOT
                / "results"
                / f"{baseline.lower()}-vs-b4-openai-gpt-5-6-luna-smoke"
                / "comparison.json"
            ).read_text(encoding="utf-8")
        )
        for baseline in ("B0", "B1", "B2", "B3")
    }

    assert all(item.treatment.method_id == "B4" for item in comparisons.values())
    assert all(item.baseline.method_id == name for name, item in comparisons.items())
    assert all(item.baseline.schema_evidence for item in comparisons.values())
    assert all(item.treatment.schema_evidence for item in comparisons.values())
    assert comparisons["B0"].improved_task_ids == []
    assert comparisons["B0"].regressed_task_ids == ["24", "47", "740"]
    assert comparisons["B1"].improved_task_ids == ["1351"]
    assert comparisons["B1"].regressed_task_ids == ["24", "740"]
    assert comparisons["B2"].improved_task_ids == ["1042", "800"]
    assert comparisons["B2"].regressed_task_ids == ["414"]
    assert comparisons["B3"].improved_task_ids == ["800"]
    assert comparisons["B3"].regressed_task_ids == ["414"]
