import json
from pathlib import Path

import yaml

from schema_safe_bench.models import SmokeRunConfig
from schema_safe_bench.reporting import write_run_artifacts
from schema_safe_bench.runner import load_run_config, run_offline_smoke


def _run_inputs(sample_database: Path, tmp_path: Path) -> SmokeRunConfig:
    databases = tmp_path / "databases" / "shop"
    databases.mkdir(parents=True)
    (databases / "shop.sqlite").write_bytes(sample_database.read_bytes())
    tasks = tmp_path / "tasks.json"
    tasks.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "List customer names",
                    "SQL": "SELECT name FROM customers ORDER BY name",
                },
                {
                    "question_id": 2,
                    "db_id": "shop",
                    "question": "Unsafe request",
                    "SQL": "SELECT count(*) FROM orders",
                },
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset": "bird-minidev-select",
                "dataset_revision": "fixture",
                "selection": "fixture",
                "seed": 1,
                "task_ids": ["1", "2"],
            }
        ),
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps({"1": "SELECT name FROM customers ORDER BY name", "2": "ABSTAIN"}),
        encoding="utf-8",
    )
    return SmokeRunConfig(
        run_id="fixture-run",
        method_id="B0",
        tasks_path=tasks,
        databases_root=tmp_path / "databases",
        manifest_path=manifest,
        predictions_path=predictions,
        output_path=tmp_path / "results" / "trace.jsonl",
    )


def test_offline_smoke_runs_end_to_end(sample_database: Path, tmp_path: Path) -> None:
    config = _run_inputs(sample_database, tmp_path)
    traces, summary = run_offline_smoke(config)

    assert summary.tasks == 2
    assert summary.correct == 1
    assert summary.abstained == 1
    assert traces[0].comparison and traces[0].comparison.equivalent
    assert traces[1].failure_label == "safe_abstention"

    trace_path, summary_path = write_run_artifacts(traces, summary, config.output_path)
    assert len(trace_path.read_text().splitlines()) == 2
    assert json.loads(summary_path.read_text())["correct"] == 1


def test_run_outputs_cannot_be_overwritten(sample_database: Path, tmp_path: Path) -> None:
    config = _run_inputs(sample_database, tmp_path)
    traces, summary = run_offline_smoke(config)
    write_run_artifacts(traces, summary, config.output_path)

    try:
        write_run_artifacts(traces, summary, config.output_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing trace should not be overwritten")


def test_load_run_config(tmp_path: Path) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "run_id": "r",
                "method_id": "B2",
                "tasks_path": "tasks.json",
                "databases_root": "db",
                "manifest_path": "manifest.json",
                "predictions_path": "predictions.json",
                "output_path": "result.jsonl",
            }
        ),
        encoding="utf-8",
    )
    assert load_run_config(config_path).method_id == "B2"
