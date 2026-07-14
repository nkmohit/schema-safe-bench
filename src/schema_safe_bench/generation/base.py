"""Model-provider boundary."""

from collections.abc import Mapping
from typing import Protocol

from schema_safe_bench.models import GenerationRequest, GenerationResponse


class Generator(Protocol):
    def generate(self, task_id: str, request: GenerationRequest) -> GenerationResponse:
        """Generate one raw response for a task."""


class OfflineGenerator:
    """Replay committed or locally saved outputs without making API calls."""

    def __init__(self, outputs: Mapping[str, str], *, model_name: str = "offline") -> None:
        self.outputs = outputs
        self.model_name = model_name

    def generate(self, task_id: str, request: GenerationRequest) -> GenerationResponse:
        del request
        try:
            output = self.outputs[task_id]
        except KeyError as exc:
            raise KeyError(f"No offline output for task {task_id!r}") from exc
        return GenerationResponse(raw_output=output, model_name=self.model_name)
