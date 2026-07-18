import hashlib
import json
from pathlib import Path

import yaml

from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]


def test_b2_policy_and_controlled_variables_are_locked() -> None:
    method = yaml.safe_load(
        (ROOT / "configs" / "methods" / "b2-bm25-schema-retrieval.yaml").read_text(encoding="utf-8")
    )
    b0 = load_hosted_run_config(ROOT / "configs" / "runs" / "b0-openai-luna-smoke.yaml")
    b1 = load_hosted_run_config(ROOT / "configs" / "runs" / "b1-openai-luna-smoke.yaml")
    b2 = load_hosted_run_config(ROOT / "configs" / "runs" / "b2-openai-luna-smoke.yaml")
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b2-bm25-schema-retrieval.json").read_text(encoding="utf-8")
    )

    assert b2.method_id == method["method_id"] == provenance["method_id"] == "B2"
    assert b2.schema_context is not None
    assert b2.schema_context.model_dump(exclude_none=True) == method["schema_context"]
    for baseline in (b0, b1):
        assert b2.tasks_path == baseline.tasks_path
        assert b2.databases_root == baseline.databases_root
        assert b2.manifest_path == baseline.manifest_path
        assert b2.model == baseline.model
        assert b2.budget == baseline.budget
        assert b2.execution == baseline.execution
    manifest = ROOT / provenance["manifest"]["path"]
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == provenance["manifest"]["sha256"]
