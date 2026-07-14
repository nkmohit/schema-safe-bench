import json
from pathlib import Path

from schema_safe_bench.datasets import verify_bird_assets, write_asset_verification


def test_verify_assets_catalogs_and_executes_reference(
    sample_database: Path, tmp_path: Path
) -> None:
    database_dir = tmp_path / "databases" / "shop"
    database_dir.mkdir(parents=True)
    (database_dir / "shop.sqlite").write_bytes(sample_database.read_bytes())
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps(
            [
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "List names",
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
                "dataset_revision": "revision",
                "selection": "fixture",
                "seed": 7,
                "task_ids": ["1"],
            }
        ),
        encoding="utf-8",
    )

    report = verify_bird_assets(
        tasks_path=tasks_path,
        databases_root=tmp_path / "databases",
        manifest_path=manifest_path,
    )

    assert report.passed_tasks == 1
    assert report.failed_tasks == 0
    assert report.database_count == 1
    assert report.checks[0].catalog_tables == 2
    assert report.checks[0].passed

    output = tmp_path / "report" / "verification.json"
    write_asset_verification(report, output)
    payload = json.loads(output.read_text())
    assert "rows" not in payload["checks"][0]
