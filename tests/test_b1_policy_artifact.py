import hashlib
import json
from pathlib import Path

import yaml

from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).resolve().parents[1]


def test_b1_policy_is_locked_to_config_and_manifest() -> None:
    method = yaml.safe_load(
        (ROOT / "configs" / "methods" / "b1-length-truncated-schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    run = load_hosted_run_config(ROOT / "configs" / "runs" / "b1-openai-luna-smoke.yaml")
    baseline = load_hosted_run_config(ROOT / "configs" / "runs" / "b0-openai-luna-smoke.yaml")
    provenance = json.loads(
        (ROOT / "data" / "provenance" / "b1-schema-truncation.json").read_text(encoding="utf-8")
    )
    manifest_path = ROOT / provenance["manifest"]["path"]

    assert run.method_id == method["method_id"] == provenance["method_id"] == "B1"
    assert run.schema_context is not None
    assert run.schema_context.model_dump(exclude_none=True) == method["schema_context"]
    assert run.schema_context.policy_id == provenance["policy_id"]
    assert run.schema_context.max_chars == provenance["max_chars"] == 1000
    assert (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() == provenance["manifest"]["sha256"]
    )
    assert provenance["smoke_manifest_effect"] == {
        "full_schema_chars_min": 395,
        "full_schema_chars_median": 1185,
        "full_schema_chars_max": 5564,
        "truncated_tasks": 15,
        "truncated_databases": 8,
        "unchanged_tasks_that_fit": 5,
    }
    assert run.model.model_name == "gpt-5.6-luna"
    assert run.model.reasoning_effort == "none"
    assert run.model.temperature == 0.0
    assert run.model.store is False
    assert run.budget.project_limit_usd < 100
    assert run.tasks_path == baseline.tasks_path
    assert run.databases_root == baseline.databases_root
    assert run.manifest_path == baseline.manifest_path
    assert run.model == baseline.model
    assert run.budget == baseline.budget
    assert run.execution == baseline.execution
