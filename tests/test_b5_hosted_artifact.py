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
B5_RESULTS = ROOT / "results" / "b5-openai-gpt-5-6-luna-smoke"
B5_RECORDING = ROOT / "data" / "processed" / "predictions" / "b5-openai-gpt-5-6-luna-smoke.json"
EVIDENCE_ROOT = ROOT / "results" / "schema-evidence-smoke"
IMPLEMENTATION_REVISION = "793b615134274d3f2b782920065a6bf192396b28"


def test_committed_b5_artifact_is_complete_consistent_and_fully_audited() -> None:
    config = load_hosted_run_config(ROOT / "configs" / "runs" / "b5-openai-luna-smoke.yaml")
    recording = GenerationRecording.model_validate_json(B5_RECORDING.read_text(encoding="utf-8"))
    trace_path = B5_RESULTS / "trace.jsonl"
    traces = [
        AuditTrace.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    summary = RunSummary.model_validate_json(
        (B5_RESULTS / "trace.summary.json").read_text(encoding="utf-8")
    )
    evidence = SchemaEvidenceReport.model_validate_json(
        (EVIDENCE_ROOT / "b5.json").read_text(encoding="utf-8")
    )
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b5-hybrid-reranking.json").read_text(encoding="utf-8")
    )

    assert config.method_id == summary.method_id == evidence.method_id == "B5"
    assert config.schema_context and config.schema_context.strategy == "hybrid_rerank"
    assert config.schema_context.embedding and config.schema_context.reranker
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

    candidate_counts = []
    candidates = []
    for trace in traces:
        assert trace.schema_pack and trace.schema_pack.retrieval_metadata
        pack = trace.schema_pack
        candidate_counts.append(len(pack.reranking_candidates))
        candidates.extend(pack.reranking_candidates)
        assert [candidate.post_rerank_rank for candidate in pack.reranking_candidates] == list(
            range(1, len(pack.reranking_candidates) + 1)
        )
        assert sorted(candidate.pre_rerank_rank for candidate in pack.reranking_candidates) == list(
            range(1, len(pack.reranking_candidates) + 1)
        )
        assert sum(candidate.selected for candidate in pack.reranking_candidates) == 12
        assert all(candidate.selected for candidate in pack.reranking_candidates[:12])
        assert not any(candidate.selected for candidate in pack.reranking_candidates[12:])
        for hit, candidate in zip(pack.retrieval_hits, pack.reranking_candidates[:12], strict=True):
            assert hit.document_id == candidate.document_id
            assert hit.rank == candidate.post_rerank_rank
            assert hit.score == candidate.reranker_score
            assert hit.component_scores == candidate.component_scores
            assert hit.component_ranks == candidate.component_ranks
            assert hit.component_contributions == candidate.component_contributions

    assert Counter(candidate_counts) == {48: 15, 41: 2, 15: 3}
    assert len(candidates) == 847
    assert all(set(candidate.component_scores) == {"bm25", "dense"} for candidate in candidates)
    assert all(set(candidate.component_ranks) == {"bm25", "dense"} for candidate in candidates)
    assert all(
        set(candidate.component_contributions) == {"bm25", "dense"} for candidate in candidates
    )
    assert all(
        math.isclose(candidate.first_stage_score, sum(candidate.component_contributions.values()))
        for candidate in candidates
    )

    metadata = [
        trace.schema_pack.retrieval_metadata
        for trace in traces
        if trace.schema_pack and trace.schema_pack.retrieval_metadata
    ]
    assert len(metadata) == 20
    assert {item.policy_id for item in metadata} == {
        "bm25-bge-rrf-minilm-rerank-schema-documents-v1"
    }
    assert {item.reranker_candidate_depth for item in metadata} == {48}
    assert {item.reranker_model_id for item in metadata} == {"cross-encoder/ms-marco-MiniLM-L6-v2"}
    assert {item.reranker_model_revision for item in metadata} == {
        "c5ee24cb16019beea0893ab7796b1df96625c6b8"
    }
    assert {item.reranker_score_interpretation for item in metadata} == {"raw_logit"}
    assert {item.reranker_truncation for item in metadata} == {"longest_first"}
    assert {item.reranker_threshold for item in metadata} == {"none"}
    assert {item.reranker_batch_size for item in metadata} == {32}
    assert {item.reranker_max_length for item in metadata} == {512}
    assert {item.reranker_software_revision for item in metadata} == {IMPLEMENTATION_REVISION}
    assert {trace.software_revision for trace in traces} == {IMPLEMENTATION_REVISION}
    assert all(trace.schema_evidence for trace in traces)

    encoded_config = json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    configuration_sha256 = hashlib.sha256(encoded_config).hexdigest()
    assert {trace.configuration_sha256 for trace in traces} == {configuration_sha256}
    assert {item.reranker_configuration_sha256 for item in metadata} == {configuration_sha256}
    assert evidence.configuration_sha256 == configuration_sha256
    assert evidence.source_trace_sha256 == hashlib.sha256(trace_path.read_bytes()).hexdigest()

    pack_digest = hashlib.sha256()
    for trace in traces:
        assert trace.schema_pack
        pack_digest.update(trace.schema_pack.model_dump_json().encode())
    assert (
        pack_digest.hexdigest()
        == provenance["pre_generation_pack_audit"]["ordered_schema_packs_sha256"]
        == "4e63da4fe763750ee0d1224bdfaa18384aea321695b05cbc133dd96495927afd"
    )

    outcomes = Counter(
        "correct" if trace.comparison and trace.comparison.equivalent else trace.failure_label
        for trace in traces
    )
    assert outcomes == {
        "correct": 2,
        "semantic_mismatch": 8,
        "safe_abstention": 8,
        "validator_rejection": 2,
    }
    assert summary.model_dump(exclude={"run_id", "method_id"}) == {
        "tasks": 20,
        "correct": 2,
        "abstained": 8,
        "invalid": 2,
        "execution_errors": 0,
        "input_tokens": 5366,
        "output_tokens": 784,
        "estimated_cost_usd": 0.01007,
    }
    assert evidence.aggregate.tasks_with_full_table_recall == 11
    assert evidence.aggregate.tasks_with_full_column_recall == 8
    assert evidence.aggregate.retrieval_misses == 12


def test_b5_paired_comparisons_include_evidence_and_exact_transitions() -> None:
    comparisons = {
        baseline: PairedRunComparison.model_validate_json(
            (
                ROOT
                / "results"
                / f"{baseline.lower()}-vs-b5-openai-gpt-5-6-luna-smoke"
                / "comparison.json"
            ).read_text(encoding="utf-8")
        )
        for baseline in ("B0", "B1", "B2", "B3", "B4")
    }

    assert all(item.treatment.method_id == "B5" for item in comparisons.values())
    assert all(item.baseline.method_id == name for name, item in comparisons.items())
    assert all(item.baseline.schema_evidence for item in comparisons.values())
    assert all(item.treatment.schema_evidence for item in comparisons.values())
    assert comparisons["B0"].improved_task_ids == []
    assert comparisons["B0"].regressed_task_ids == ["24", "47", "740", "800"]
    assert comparisons["B1"].improved_task_ids == ["1351"]
    assert comparisons["B1"].regressed_task_ids == ["24", "740", "800"]
    assert comparisons["B2"].improved_task_ids == ["1042"]
    assert comparisons["B2"].regressed_task_ids == ["414"]
    assert comparisons["B3"].improved_task_ids == []
    assert comparisons["B3"].regressed_task_ids == ["414"]
    assert comparisons["B4"].improved_task_ids == []
    assert comparisons["B4"].regressed_task_ids == ["800"]
