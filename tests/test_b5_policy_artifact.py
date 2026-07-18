import hashlib
import json
from pathlib import Path

import yaml

from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]


def test_b5_reranking_policy_and_controlled_variables_are_locked() -> None:
    method = yaml.safe_load(
        (ROOT / "configs" / "methods" / "b5-hybrid-reranking.yaml").read_text(encoding="utf-8")
    )
    baselines = [
        load_hosted_run_config(ROOT / "configs" / "runs" / f"b{i}-openai-luna-smoke.yaml")
        for i in range(5)
    ]
    b5 = load_hosted_run_config(ROOT / "configs" / "runs" / "b5-openai-luna-smoke.yaml")
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b5-hybrid-reranking.json").read_text(encoding="utf-8")
    )

    assert b5.method_id == method["method_id"] == provenance["method_id"] == "B5"
    assert b5.schema_context is not None
    assert b5.schema_context.reranker is not None
    assert b5.schema_context.model_dump(exclude_none=True, mode="json") == method["schema_context"]
    assert b5.schema_context.reranker_candidate_depth == 48
    assert b5.schema_context.top_k == 12
    assert b5.schema_context.candidate_depth == "all_documents"
    assert b5.schema_context.lexical_weight == 1.0
    assert b5.schema_context.dense_weight == 1.0
    assert b5.schema_context.rank_constant == 60
    assert b5.schema_context.reranker.revision == provenance["reranker"]["revision"]
    assert b5.schema_context.reranker.score_interpretation == "raw_logit"
    assert provenance["reranker"]["threshold"] == "none"
    assert provenance["reranker"]["license"] == "Apache-2.0"
    assert provenance["pre_generation_pack_audit"] == {
        "inputs": "public questions and database catalogs only",
        "tasks": 20,
        "databases": 10,
        "configured_candidate_depth": 48,
        "candidate_count_distribution": {"15": 3, "41": 2, "48": 15},
        "reranked_candidates": 847,
        "selected_hits": 240,
        "schema_chars_total": 12985,
        "database_embedding_caches": 10,
        "ordered_schema_packs_sha256": (
            "4e63da4fe763750ee0d1224bdfaa18384aea321695b05cbc133dd96495927afd"
        ),
        "independent_process_digests_matched": True,
        "implementation_revision": "793b615134274d3f2b782920065a6bf192396b28",
    }
    for name, digest in provenance["reranker"]["files"].items():
        assert len(digest) == 64, name
    for baseline in baselines:
        assert b5.tasks_path == baseline.tasks_path
        assert b5.databases_root == baseline.databases_root
        assert b5.manifest_path == baseline.manifest_path
        assert b5.model == baseline.model
        assert b5.budget == baseline.budget
        assert b5.execution == baseline.execution
    manifest = ROOT / provenance["manifest"]["path"]
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == provenance["manifest"]["sha256"]


def test_b0_through_b4_configs_do_not_gain_serialized_reranker_fields() -> None:
    for method_id in range(5):
        config = load_hosted_run_config(
            ROOT / "configs" / "runs" / f"b{method_id}-openai-luna-smoke.yaml"
        )
        encoded = config.model_dump_json(exclude_none=True)
        assert "reranker" not in encoded
        assert "hybrid_rerank" not in encoded
