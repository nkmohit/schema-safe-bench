"""Deterministic hosted-response recording and replay."""

import hashlib
import json
from pathlib import Path

from schema_safe_bench.models import (
    GenerationRecord,
    GenerationRecording,
    GenerationRequest,
    GenerationResponse,
    RepairRecord,
    RepairRecording,
)


def request_sha256(task_id: str, request: GenerationRequest) -> str:
    payload = {
        "task_id": task_id,
        "request": request.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def repair_request_sha256(task_id: str, stage: str, request: GenerationRequest) -> str:
    payload = {
        "task_id": task_id,
        "stage": stage,
        "request": request.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_recording(path: Path, *, model_name: str) -> GenerationRecording:
    if not path.exists():
        return GenerationRecording(requested_model_name=model_name)
    recording = GenerationRecording.model_validate_json(path.read_text(encoding="utf-8"))
    if recording.requested_model_name != model_name:
        raise ValueError("recording model does not match the configured hosted model")
    if len({record.task_id for record in recording.records}) != len(recording.records):
        raise ValueError("recording task IDs must be unique")
    return recording


def load_recording_with_sources(
    path: Path, *, source_paths: list[Path], model_name: str
) -> GenerationRecording:
    """Merge immutable replay sources into a distinct writable recording."""
    merged = load_recording(path, model_name=model_name)
    by_task = {record.task_id: record for record in merged.records}
    for source_path in source_paths:
        if source_path == path:
            raise ValueError("recording replay source must differ from the writable recording")
        source = load_recording(source_path, model_name=model_name)
        for record in source.records:
            existing = by_task.get(record.task_id)
            if existing is not None and existing != record:
                raise ValueError(f"conflicting replay source for task {record.task_id!r}")
            by_task[record.task_id] = record
    merged.records = sorted(by_task.values(), key=lambda item: item.task_id)
    return merged


def load_repair_recording(path: Path, *, model_name: str) -> RepairRecording:
    if not path.exists():
        return RepairRecording(requested_model_name=model_name)
    recording = RepairRecording.model_validate_json(path.read_text(encoding="utf-8"))
    if recording.requested_model_name != model_name:
        raise ValueError("repair recording model does not match the configured hosted model")
    keys = {(record.task_id, record.stage) for record in recording.records}
    if len(keys) != len(recording.records):
        raise ValueError("repair recording task-stage keys must be unique")
    return recording


def load_repair_recording_with_sources(
    path: Path, *, source_paths: list[Path], model_name: str
) -> RepairRecording:
    """Merge immutable repair sources into a distinct writable recording."""
    merged = load_repair_recording(path, model_name=model_name)
    by_key = {(record.task_id, record.stage): record for record in merged.records}
    for source_path in source_paths:
        if source_path == path:
            raise ValueError("repair replay source must differ from the writable recording")
        source = load_repair_recording(source_path, model_name=model_name)
        for record in source.records:
            key = (record.task_id, record.stage)
            existing = by_key.get(key)
            if existing is not None and existing != record:
                raise ValueError(f"conflicting repair replay source for task-stage {key!r}")
            by_key[key] = record
    merged.records = sorted(by_key.values(), key=lambda item: (item.task_id, item.stage))
    return merged


def recorded_response(
    recording: GenerationRecording,
    *,
    task_id: str,
    expected_request_sha256: str,
) -> GenerationResponse | None:
    record = next((item for item in recording.records if item.task_id == task_id), None)
    if record is None:
        return None
    if record.request_sha256 != expected_request_sha256:
        raise ValueError(f"recorded request digest does not match task {task_id!r}")
    return record.response.model_copy(update={"replayed": True})


def recorded_repair_response(
    recording: RepairRecording,
    *,
    task_id: str,
    stage: str,
    expected_request_sha256: str,
) -> GenerationResponse | None:
    record = next(
        (item for item in recording.records if item.task_id == task_id and item.stage == stage),
        None,
    )
    if record is None:
        return None
    if record.request_sha256 != expected_request_sha256:
        raise ValueError(f"recorded repair request digest does not match task {task_id!r}")
    return record.response.model_copy(update={"replayed": True})


def save_record(
    recording: GenerationRecording,
    path: Path,
    *,
    task_id: str,
    digest: str,
    response: GenerationResponse,
) -> None:
    if any(record.task_id == task_id for record in recording.records):
        raise ValueError(f"task {task_id!r} is already recorded")
    recording.records.append(
        GenerationRecord(task_id=task_id, request_sha256=digest, response=response)
    )
    recording.records.sort(key=lambda item: item.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(recording.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def save_repair_record(
    recording: RepairRecording,
    path: Path,
    *,
    task_id: str,
    stage: str,
    digest: str,
    response: GenerationResponse,
) -> None:
    if any(item.task_id == task_id and item.stage == stage for item in recording.records):
        raise ValueError(f"repair recording already contains task-stage {task_id!r}/{stage!r}")
    record = RepairRecord(
        task_id=task_id,
        stage=stage,
        request_sha256=digest,
        response=response,
    )
    recording.records.append(record)
    recording.records.sort(key=lambda item: (item.task_id, item.stage))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(recording.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
