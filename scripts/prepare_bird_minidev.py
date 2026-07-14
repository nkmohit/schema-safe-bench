"""Verify and safely extract an official BIRD Mini-Dev archive."""

import argparse
import hashlib
import shutil
import stat
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


def _extract_zip(archive: zipfile.ZipFile, destination: Path, prefix: PurePosixPath | None) -> None:
    destination_root = destination.resolve()
    selected = 0
    for member in _safe_zip_members(archive):
        member_path = PurePosixPath(member.filename)
        if prefix is not None:
            try:
                member_path = member_path.relative_to(prefix)
            except ValueError:
                continue
        if not member_path.parts or member_path.name == ".DS_Store":
            continue
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symbolic links are not allowed: {member.filename}")
        target = destination.joinpath(*member_path.parts).resolve()
        if not target.is_relative_to(destination_root):
            raise ValueError(f"Unsafe archive member: {member.filename}")
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        selected += 1
    if selected == 0:
        label = str(prefix) if prefix is not None else "archive"
        raise ValueError(f"No files found under {label!r}")


def extract_archive(archive_path: Path, destination: Path, *, prefix: str | None = None) -> None:
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                _extract_zip(
                    archive,
                    destination,
                    PurePosixPath(prefix.strip("/")) if prefix else None,
                )
        elif tarfile.is_tarfile(archive_path):
            if prefix:
                raise ValueError("Prefix extraction is currently supported for ZIP archives only")
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
    parser.add_argument(
        "--prefix",
        help="Extract only this ZIP subtree and remove the prefix from output paths",
    )
    args = parser.parse_args()

    if not args.archive.is_file():
        parser.error(f"Archive does not exist: {args.archive}")
    actual = sha256(args.archive)
    if actual.casefold() != args.sha256.casefold():
        parser.error(f"SHA-256 mismatch: expected {args.sha256}, got {actual}")
    extract_archive(args.archive, args.destination, prefix=args.prefix)
    print(f"Verified {actual} and extracted into {args.destination}")


if __name__ == "__main__":
    main()
