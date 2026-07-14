"""Verify and safely extract an official BIRD Mini-Dev archive."""

import argparse
import hashlib
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe archive member: {member.filename}")
    return members


def extract_archive(archive_path: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(destination, members=_safe_zip_members(archive))
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path) as archive:
                archive.extractall(destination, filter="data")
        else:
            raise ValueError("Expected a ZIP or TAR-compatible archive")
    except Exception:
        shutil.rmtree(destination)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="Expected archive SHA-256 digest")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    if not args.archive.is_file():
        parser.error(f"Archive does not exist: {args.archive}")
    actual = sha256(args.archive)
    if actual.casefold() != args.sha256.casefold():
        parser.error(f"SHA-256 mismatch: expected {args.sha256}, got {actual}")
    extract_archive(args.archive, args.destination)
    print(f"Verified {actual} and extracted into {args.destination}")


if __name__ == "__main__":
    main()
