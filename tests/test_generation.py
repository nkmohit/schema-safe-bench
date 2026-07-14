import pytest

from schema_safe_bench.generation import OfflineGenerator
from schema_safe_bench.models import GenerationRequest, PromptMessage


def _request() -> GenerationRequest:
    return GenerationRequest(
        messages=[PromptMessage(role="user", content="question")],
        model_name="fixture",
        prompt_version="fixture-v1",
    )


def test_offline_generator_replays_raw_output() -> None:
    response = OfflineGenerator({"task-1": "SELECT 1"}).generate("task-1", _request())
    assert response.raw_output == "SELECT 1"
    assert response.model_name == "offline"


def test_offline_generator_requires_task_output() -> None:
    with pytest.raises(KeyError, match="No offline output"):
        OfflineGenerator({}).generate("missing", _request())
