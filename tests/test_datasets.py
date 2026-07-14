import json
from pathlib import Path

import pytest

from schema_safe_bench.datasets import build_manifest, find_database, load_bird_tasks


def _write_tasks(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "question_id": 2,
                    "db_id": "shop",
                    "question": "Names?",
                    "SQL": "SELECT name FROM customers",
                },
                {
                    "question_id": 1,
                    "db_id": "shop",
                    "question": "Count?",
                    "SQL": "SELECT count(*) FROM orders",
                    "evidence": "orders",
                },
                {
                    "question_id": 3,
                    "db_id": "shop",
                    "question": "Remove?",
                    "SQL": "DELETE FROM orders",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_load_bird_tasks_normalizes_and_filters(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    _write_tasks(path)

    tasks = load_bird_tasks(path)

    assert [task.task_id for task in tasks] == ["2", "1"]
    assert tasks[1].evidence == "orders"
    assert tasks[0].reference_sql == "SELECT name FROM customers"


def test_manifest_is_independent_of_input_order(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    _write_tasks(path)
    tasks = load_bird_tasks(path)

    first = build_manifest(tasks, count=2, seed=7, dataset_revision="fixture")
    second = build_manifest(list(reversed(tasks)), count=2, seed=7, dataset_revision="fixture")

    assert first == second
    assert len(first.task_ids) == 2


def test_manifest_rejects_invalid_count(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    _write_tasks(path)
    tasks = load_bird_tasks(path)

    with pytest.raises(ValueError, match="requested"):
        build_manifest(tasks, count=3, seed=7, dataset_revision="fixture")


def test_find_database_stays_inside_root(sample_database: Path, tmp_path: Path) -> None:
    db_dir = tmp_path / "databases" / "shop"
    db_dir.mkdir(parents=True)
    target = db_dir / "shop.sqlite"
    target.write_bytes(sample_database.read_bytes())

    assert find_database(tmp_path / "databases", "shop") == target
    with pytest.raises(FileNotFoundError):
        find_database(tmp_path / "databases", "../shop")


def test_invalid_dataset_shape_fails(tmp_path: Path) -> None:
    path = tmp_path / "tasks.json"
    path.write_text('{"unexpected": true}', encoding="utf-8")

    with pytest.raises(ValueError, match="list of task objects"):
        load_bird_tasks(path)
