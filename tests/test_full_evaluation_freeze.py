import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from schema_safe_bench.datasets import build_full_evaluation_population
from schema_safe_bench.evaluation.freeze import (
    file_sha256,
    freeze_full_evaluation,
    load_freeze_config,
)
from schema_safe_bench.generation import load_recording_with_sources, request_sha256, save_record
from schema_safe_bench.models import (
    AssetTaskCheck,
    AssetVerificationReport,
    AuditTrace,
    DatabaseInventory,
    FullEvaluationExclusionReport,
    FullEvaluationFreezeConfig,
    FullEvaluationFreezeReport,
    FullEvaluationManifest,
    GenerationRecord,
    GenerationRecording,
    GenerationResponse,
    RepairRecording,
)
from schema_safe_bench.prompting import build_generation_request
from schema_safe_bench.runner import load_hosted_run_config

ROOT = Path(__file__).parents[1]
FREEZE_CONFIG = ROOT / "configs/evaluation/bird-minidev-b0-b7-full-freeze.yaml"
MANIFEST = ROOT / "data/processed/manifests/bird-minidev-select-full.json"
EXCLUSIONS = ROOT / "data/processed/manifests/bird-minidev-select-full-exclusions.json"
INVENTORY = ROOT / "data/provenance/bird-minidev-full-databases.json"
REPORT = ROOT / "results/full-evaluation-readiness.json"


def test_population_is_input_order_independent_and_structural(tmp_path: Path) -> None:
    records = [
        {
            "question_id": 11,
            "db_id": "db_b",
            "question": "Second",
            "SQL": "SELECT 2",
            "difficulty": "moderate",
        },
        {
            "question_id": 2,
            "db_id": "db_a",
            "question": "First",
            "SQL": "SELECT 1",
            "difficulty": "simple",
        },
        {
            "question_id": 12,
            "db_id": "db_b",
            "question": "Rejected",
            "SQL": "DELETE FROM secret",
            "difficulty": "challenging",
        },
    ]
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(records), encoding="utf-8")
    second.write_text(json.dumps(list(reversed(records))), encoding="utf-8")
    first_manifest, first_exclusions, _ = build_full_evaluation_population(
        first, dataset_revision="revision"
    )
    second_manifest, second_exclusions, _ = build_full_evaluation_population(
        second, dataset_revision="revision"
    )
    assert first_manifest.task_ids == second_manifest.task_ids == ["2", "11"]
    assert first_manifest.population_sha256 == second_manifest.population_sha256
    assert first_exclusions.exclusions == second_exclusions.exclusions
    assert first_exclusions.reason_counts["not_single_select_query"] == 1
    assert first_exclusions.prohibited_decision_inputs == [
        "model_output",
        "execution_result",
        "evaluator_label",
        "equivalence_outcome",
    ]


def test_committed_full_population_and_budget_constraint() -> None:
    manifest = FullEvaluationManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    exclusions = FullEvaluationExclusionReport.model_validate_json(
        EXCLUSIONS.read_text(encoding="utf-8")
    )
    inventory = DatabaseInventory.model_validate_json(INVENTORY.read_text(encoding="utf-8"))
    report = FullEvaluationFreezeReport.model_validate_json(REPORT.read_text(encoding="utf-8"))
    assert manifest.task_count == exclusions.included_count == report.task_count == 500
    assert exclusions.excluded_count == 0
    assert manifest.database_count == inventory.database_count == report.database_count == 11
    assert manifest.difficulty_counts == {"challenging": 102, "moderate": 250, "simple": 148}
    assert report.protocol_status == "blocked_by_budget_and_verification"
    assert report.expanded_execution_authorized is False
    assert report.project_limit_usd == 95
    assert report.within_project_limit is True
    assert report.projected_reservation_usd + report.ledger_spent_usd < 100
    assert report.reference_tasks_passed == 428
    assert report.reference_tasks_failed == 72
    assert {plan.method_id for plan in report.methods if not plan.within_run_limit} == {
        "B0",
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "B6",
    }


def test_full_configs_are_paired_and_distinct_from_smoke() -> None:
    freeze = load_freeze_config(FREEZE_CONFIG)
    full = [load_hosted_run_config(ROOT / path) for path in freeze.run_config_paths]
    smoke = [
        load_hosted_run_config(ROOT / f"configs/runs/b{index}-openai-luna-smoke.yaml")
        for index in range(8)
    ]
    assert [config.method_id for config in full] == [f"B{index}" for index in range(8)]
    assert len({config.output_path for config in full}) == 8
    for full_config, smoke_config in zip(full, smoke, strict=True):
        assert full_config.manifest_path == freeze.manifest_path
        assert full_config.output_path != smoke_config.output_path
        assert full_config.model == smoke_config.model
        assert full_config.budget == smoke_config.budget
        assert full_config.execution == smoke_config.execution
        assert full_config.schema_context == smoke_config.schema_context


def test_replay_sources_merge_without_mutating_smoke_recording(tmp_path: Path) -> None:
    source = ROOT / "data/processed/predictions/b0-openai-gpt-5-6-luna-smoke.json"
    source_digest = file_sha256(source)
    target = tmp_path / "full.json"
    recording = load_recording_with_sources(
        target, source_paths=[source], model_name="gpt-5.6-luna"
    )
    assert len(recording.records) == 20
    save_record(
        recording,
        target,
        task_id="full-only",
        digest="0" * 64,
        response=GenerationResponse(
            status="completed",
            raw_output="SELECT 1",
            model_name="gpt-5.6-luna",
            requested_model_name="gpt-5.6-luna",
            provider="openai",
            endpoint="responses",
            input_tokens=1,
            output_tokens=1,
        ),
    )
    assert len(json.loads(target.read_text())["records"]) == 21
    assert file_sha256(source) == source_digest


def test_evaluator_only_task_mutation_cannot_change_generation_request() -> None:
    trace = json.loads(
        (ROOT / "results/b4-openai-gpt-5-6-luna-smoke/trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    task = {
        "question": trace["question"],
        "SQL": "SELECT evaluator_only_reference",
        "evidence": "evaluator-only evidence",
    }
    config = load_hosted_run_config(ROOT / "configs/runs/b4-openai-luna-smoke.yaml")
    from schema_safe_bench.models import SchemaPack

    schema_pack = SchemaPack.model_validate(trace["schema_pack"])
    before = build_generation_request(
        question=task["question"], schema_pack=schema_pack, model_name=config.model.model_name
    )
    task["SQL"] = "SELECT evaluator_only_mutation"
    task["evidence"] = "evaluator-only evidence mutation"
    after = build_generation_request(
        question=task["question"], schema_pack=schema_pack, model_name=config.model.model_name
    )
    assert before == after


def test_freeze_artifacts_regenerate_from_pinned_local_assets() -> None:
    freeze = load_freeze_config(FREEZE_CONFIG)
    tasks_path = ROOT / freeze.tasks_path
    if not tasks_path.exists():
        pytest.skip("public raw benchmark assets are intentionally not committed")
    manifest, exclusions, _ = build_full_evaluation_population(
        tasks_path, dataset_revision=freeze.dataset_revision
    )
    assert manifest == FullEvaluationManifest.model_validate_json(MANIFEST.read_text())
    assert exclusions == FullEvaluationExclusionReport.model_validate_json(EXCLUSIONS.read_text())
    provenance = json.loads((ROOT / freeze.dataset_provenance_path).read_text())
    assert file_sha256(tasks_path) == provenance["task_records"]["sha256"]
    inventory = DatabaseInventory.model_validate_json(INVENTORY.read_text())
    for asset in inventory.databases:
        database = ROOT / freeze.databases_root / asset.relative_path
        assert database.stat().st_size == asset.size_bytes
        assert file_sha256(database) == asset.sha256


def test_provider_free_freeze_runs_end_to_end_on_tiny_assets(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "tiny",
                    "question": "Return one",
                    "SQL": "SELECT 1",
                    "difficulty": "simple",
                }
            ]
        ),
        encoding="utf-8",
    )
    databases = tmp_path / "databases"
    database = databases / "tiny" / "tiny.sqlite"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE values_table (value INTEGER)")

    provenance = tmp_path / "dataset-provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "task_records": {
                    "revision": "tiny-revision",
                    "sha256": file_sha256(tasks_path),
                },
                "database_archive": {"sha256": "a" * 64, "size_bytes": 1},
            }
        ),
        encoding="utf-8",
    )
    evaluator = tmp_path / "evaluator.json"
    evaluator.write_text("{}\n", encoding="utf-8")
    asset_verification = tmp_path / "verification.json"
    asset_verification.write_text(
        AssetVerificationReport(
            dataset="bird-minidev-select",
            dataset_revision="tiny-revision",
            manifest_seed=None,
            task_count=1,
            database_count=1,
            passed_tasks=1,
            failed_tasks=0,
            checks=[
                AssetTaskCheck(
                    task_id="1",
                    db_id="tiny",
                    catalog_tables=1,
                    validation_status="valid",
                    execution_status="success",
                    truncated=False,
                )
            ],
        ).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "manifest.json"
    run_paths: list[Path] = []
    reusable_recordings: dict[str, Path] = {}
    reusable_traces: dict[str, Path] = {}
    for index in range(6):
        method_id = f"B{index}"
        smoke_config = load_hosted_run_config(
            ROOT / f"configs/runs/b{index}-openai-luna-smoke.yaml"
        )
        base_trace = AuditTrace.model_validate_json(
            (ROOT / f"results/b{index}-openai-gpt-5-6-luna-smoke/trace.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert base_trace.schema_pack and base_trace.generation
        request = build_generation_request(
            question="Return one",
            schema_pack=base_trace.schema_pack,
            model_name=smoke_config.model.model_name,
            temperature=smoke_config.model.temperature,
            max_output_tokens=smoke_config.model.max_output_tokens,
            reasoning_effort=smoke_config.model.reasoning_effort,
        )
        digest = request_sha256("1", request)
        source_recording = tmp_path / f"{method_id}-source.json"
        source_recording.write_text(
            GenerationRecording(
                requested_model_name="gpt-5.6-luna",
                records=[
                    GenerationRecord(
                        task_id="1", request_sha256=digest, response=base_trace.generation
                    )
                ],
            ).model_dump_json(indent=2)
            + "\n",
            encoding="utf-8",
        )
        source_trace = tmp_path / f"{method_id}-trace.jsonl"
        source_trace.write_text(
            base_trace.model_copy(
                update={
                    "task_id": "1",
                    "db_id": "tiny",
                    "question": "Return one",
                    "method_id": method_id,
                    "request_sha256": digest,
                }
            ).model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        reusable_recordings[method_id] = source_recording
        reusable_traces[method_id] = source_trace

    b6_repair_source = tmp_path / "B6-repair-source.json"
    b6_repair_source.write_text(
        RepairRecording(requested_model_name="gpt-5.6-luna").model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    reusable_recordings["B6"] = b6_repair_source

    for index in range(8):
        method_id = f"B{index}"
        smoke_config = load_hosted_run_config(
            ROOT / f"configs/runs/b{index}-openai-luna-smoke.yaml"
        )
        payload = smoke_config.model_dump(mode="json", exclude_none=True, by_alias=True)
        payload.update(
            {
                "run_id": f"tiny-{method_id}",
                "tasks_path": str(tasks_path),
                "databases_root": str(databases),
                "manifest_path": str(manifest_path),
                "output_path": str(tmp_path / f"{method_id}-output.jsonl"),
            }
        )
        payload["budget"]["ledger_path"] = str(tmp_path / "ledger.json")
        if index <= 5:
            payload["recording_path"] = str(tmp_path / f"{method_id}-full-recording.json")
            payload["replay_source_paths"] = [str(reusable_recordings[method_id])]
        else:
            payload["recording_path"] = str(tmp_path / "B4-full-recording.json")
            payload["reliability"]["first_pass_config_path"] = str(tmp_path / "B4-full-config.yaml")
            payload["reliability"]["first_pass_recording_path"] = str(
                tmp_path / "B4-full-recording.json"
            )
            payload["reliability"]["first_pass_trace_path"] = str(tmp_path / "B4-full-output.jsonl")
            if index == 6:
                payload["reliability"]["repair_recording_path"] = str(
                    tmp_path / "B6-full-repair.json"
                )
                payload["reliability"]["repair_replay_source_paths"] = [str(b6_repair_source)]
        run_path = tmp_path / f"{method_id}-full-config.yaml"
        run_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        run_paths.append(run_path)

    report = freeze_full_evaluation(
        FullEvaluationFreezeConfig(
            dataset_revision="tiny-revision",
            tasks_path=tasks_path,
            databases_root=databases,
            dataset_provenance_path=provenance,
            evaluator_provenance_path=evaluator,
            manifest_path=manifest_path,
            exclusion_report_path=tmp_path / "exclusions.json",
            database_inventory_path=tmp_path / "inventory.json",
            asset_verification_path=asset_verification,
            report_path=tmp_path / "report.json",
            run_config_paths=run_paths,
            reusable_recording_paths=reusable_recordings,
            reusable_trace_paths=reusable_traces,
        )
    )
    assert report.protocol_status == "frozen"
    assert report.task_count == report.database_count == report.reference_tasks_passed == 1
    assert report.unique_missing_request_upper_bound == 1
    assert report.methods[-1].reservation_usd == 0
