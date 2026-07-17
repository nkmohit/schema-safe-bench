import hashlib
import json
from pathlib import Path

import pytest

from schema_safe_bench.evaluation.compatibility import (
    build_edge_case_cross_check,
    load_official_calculate_ex,
    run_evaluator_compatibility,
    write_compatibility_report,
)

OFFICIAL_FIXTURE = """def calculate_ex(predicted_res, ground_truth_res):
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res
"""


def _official_checkout(tmp_path: Path) -> tuple[Path, str, str]:
    checkout = tmp_path / "official"
    evaluation = checkout / "evaluation"
    evaluation.mkdir(parents=True)
    ex_path = evaluation / "evaluation_ex.py"
    utils_path = evaluation / "evaluation_utils.py"
    ex_path.write_text(OFFICIAL_FIXTURE, encoding="utf-8")
    utils_path.write_text("# fixture\n", encoding="utf-8")
    ex_sha = hashlib.sha256(ex_path.read_bytes()).hexdigest()
    utils_sha = hashlib.sha256(utils_path.read_bytes()).hexdigest()
    return checkout, ex_sha, utils_sha


def test_edge_cases_match_pinned_official_function(tmp_path: Path) -> None:
    checkout, ex_sha, _ = _official_checkout(tmp_path)
    calculate = load_official_calculate_ex(
        checkout / "evaluation" / "evaluation_ex.py", expected_sha256=ex_sha
    )
    cases = build_edge_case_cross_check(calculate)

    assert len(cases) == 7
    assert all(case.matched for case in cases)
    assert {case.name for case in cases} >= {
        "row_order",
        "duplicate_rows",
        "null_values",
        "integer_float_equality",
        "numeric_precision",
        "execution_error",
    }


def test_checksum_mismatch_rejects_unpinned_source(tmp_path: Path) -> None:
    checkout, _, _ = _official_checkout(tmp_path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_official_calculate_ex(
            checkout / "evaluation" / "evaluation_ex.py", expected_sha256="0" * 64
        )


def test_smoke_compatibility_runs_both_execution_paths(
    sample_database: Path, tmp_path: Path
) -> None:
    checkout, ex_sha, utils_sha = _official_checkout(tmp_path)
    databases = tmp_path / "databases" / "shop"
    databases.mkdir(parents=True)
    (databases / "shop.sqlite").write_bytes(sample_database.read_bytes())
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "Names",
                    "SQL": "SELECT name FROM customers ORDER BY name",
                }
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset": "fixture",
                "dataset_revision": "fixture-revision",
                "selection": "fixture",
                "seed": 1,
                "task_ids": ["1"],
            }
        ),
        encoding="utf-8",
    )

    report = run_evaluator_compatibility(
        official_checkout=checkout,
        tasks_path=tasks_path,
        databases_root=tmp_path / "databases",
        manifest_path=manifest_path,
        evaluation_ex_sha256=ex_sha,
        evaluation_utils_sha256=utils_sha,
        repository_revision="fixture-head",
        evaluator_revision="fixture-evaluator",
        verify_git_revision=False,
    )

    assert report.edge_case_matches == report.edge_case_count
    assert report.smoke_task_matches == report.smoke_task_count == 1
    assert not report.mismatches
    assert report.smoke_checks[0].result_rows == 2

    output = tmp_path / "report.json"
    write_compatibility_report(report, output)
    assert json.loads(output.read_text())["comparison_policy"] == "bird-execution-v1"
