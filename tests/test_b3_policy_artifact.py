import hashlib
import json
from pathlib import Path

import yaml

from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]


def test_b3_policy_model_revision_and_controlled_variables_are_locked() -> None:
    method = yaml.safe_load(
        (ROOT / "configs" / "methods" / "b3-dense-schema-retrieval.yaml").read_text(
            encoding="utf-8"
        )
    )
    baselines = [
        load_hosted_run_config(ROOT / "configs" / "runs" / f"b{i}-openai-luna-smoke.yaml")
        for i in range(3)
    ]
    b3 = load_hosted_run_config(ROOT / "configs" / "runs" / "b3-openai-luna-smoke.yaml")
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b3-dense-schema-retrieval.json").read_text(
            encoding="utf-8"
        )
    )

    assert b3.method_id == method["method_id"] == provenance["method_id"] == "B3"
    assert b3.schema_context is not None and b3.schema_context.embedding is not None
    assert b3.schema_context.model_dump(exclude_none=True, mode="json") == method["schema_context"]
    assert b3.schema_context.embedding.model_id == provenance["embedding_model"]["model_id"]
    assert b3.schema_context.embedding.revision == provenance["embedding_model"]["revision"]
    for baseline in baselines:
        assert b3.tasks_path == baseline.tasks_path
        assert b3.databases_root == baseline.databases_root
        assert b3.manifest_path == baseline.manifest_path
        assert b3.model == baseline.model
        assert b3.budget == baseline.budget
        assert b3.execution == baseline.execution
    manifest = ROOT / provenance["manifest"]["path"]
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == provenance["manifest"]["sha256"]
