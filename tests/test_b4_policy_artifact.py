import hashlib
import json
from pathlib import Path

import yaml

from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]


def test_b4_fusion_policy_and_controlled_variables_are_locked() -> None:
    method = yaml.safe_load(
        (ROOT / "configs" / "methods" / "b4-hybrid-schema-retrieval.yaml").read_text(
            encoding="utf-8"
        )
    )
    baselines = [
        load_hosted_run_config(ROOT / "configs" / "runs" / f"b{i}-openai-luna-smoke.yaml")
        for i in range(4)
    ]
    b4 = load_hosted_run_config(ROOT / "configs" / "runs" / "b4-openai-luna-smoke.yaml")
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b4-hybrid-schema-retrieval.json").read_text(
            encoding="utf-8"
        )
    )

    assert b4.method_id == method["method_id"] == provenance["method_id"] == "B4"
    assert b4.schema_context is not None and b4.schema_context.embedding is not None
    assert b4.schema_context.model_dump(exclude_none=True, mode="json") == method["schema_context"]
    assert b4.schema_context.k1 == provenance["lexical_component"]["k1"] == 1.5
    assert b4.schema_context.b == provenance["lexical_component"]["b"] == 0.75
    assert b4.schema_context.epsilon == provenance["lexical_component"]["epsilon"] == 0.25
    assert b4.schema_context.embedding.revision == provenance["dense_component"]["revision"]
    assert b4.schema_context.candidate_depth == "all_documents"
    assert b4.schema_context.lexical_weight == provenance["fusion"]["lexical_weight"] == 1.0
    assert b4.schema_context.dense_weight == provenance["fusion"]["dense_weight"] == 1.0
    assert b4.schema_context.rank_constant == provenance["fusion"]["rank_constant"] == 60
    assert provenance["fusion"]["doi"] == "10.1145/1571941.1572114"
    assert provenance["pre_generation_pack_audit"] == {
        "inputs": "public questions and database catalogs only",
        "tasks": 20,
        "databases": 10,
        "retrieval_hits": 240,
        "schema_chars_total": 17450,
        "ordered_schema_packs_sha256": (
            "021dfecc493ad1b747679116a256173975cc740327f2331bac9519b7d621c469"
        ),
        "independent_process_digests_matched": True,
    }
    for baseline in baselines:
        assert b4.tasks_path == baseline.tasks_path
        assert b4.databases_root == baseline.databases_root
        assert b4.manifest_path == baseline.manifest_path
        assert b4.model == baseline.model
        assert b4.budget == baseline.budget
        assert b4.execution == baseline.execution
    manifest = ROOT / provenance["manifest"]["path"]
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == provenance["manifest"]["sha256"]
