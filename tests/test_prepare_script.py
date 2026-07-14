import importlib.util
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_bird_minidev.py"
SPEC = importlib.util.spec_from_file_location("prepare_bird_minidev", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_hash_and_safe_extract(tmp_path: Path) -> None:
    archive_path = tmp_path / "bird.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("mini_dev_data/mini_dev_sqlite.json", "[]")

    destination = tmp_path / "prepared"
    digest = MODULE.sha256(archive_path)
    MODULE.extract_archive(archive_path, destination)

    assert len(digest) == 64
    assert (destination / "mini_dev_data" / "mini_dev_sqlite.json").is_file()


def test_zip_traversal_is_rejected_and_cleaned_up(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")

    destination = tmp_path / "prepared"
    with pytest.raises(ValueError, match="Unsafe archive member"):
        MODULE.extract_archive(archive_path, destination)

    assert not destination.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_existing_destination_is_preserved(tmp_path: Path) -> None:
    archive_path = tmp_path / "bird.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("file.txt", "content")
    destination = tmp_path / "prepared"
    destination.mkdir()

    with pytest.raises(FileExistsError):
        MODULE.extract_archive(archive_path, destination)
