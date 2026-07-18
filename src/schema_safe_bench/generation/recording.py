"""Deterministic hosted-response recording and replay."""

import hashlib
import json
from pathlib import Path

from schema_safe_bench.models import (
    GenerationRecord,
    GenerationRecording,
    GenerationRequest,
    GenerationResponse,
)


def request_sha256(task_id: str, request: GenerationRequest) -> str:
    payload = {
        "task_id": task_id,
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
