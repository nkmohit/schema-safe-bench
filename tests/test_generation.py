from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from schema_safe_bench.generation import (
    OfflineGenerator,
    OpenAIResponsesGenerator,
    SpendLedger,
    load_recording,
    maximum_request_cost,
    recorded_response,
    request_sha256,
    response_cost,
    save_record,
)
from schema_safe_bench.models import (
    GenerationRequest,
    GenerationResponse,
    HostedModelConfig,
    PromptMessage,
    SpendBudgetConfig,
)


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


class _FakeResponses:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        usage = SimpleNamespace(
            input_tokens=120,
            output_tokens=20,
            input_tokens_details=SimpleNamespace(cached_tokens=40),
        )
        return SimpleNamespace(
            output_text="SELECT 1",
            model="gpt-5.6-luna",
            status="completed",
            usage=usage,
        )


def test_openai_responses_adapter_is_stateless_and_records_usage() -> None:
    responses = _FakeResponses()
    client = SimpleNamespace(responses=responses)
    settings = HostedModelConfig()
    request = _request().model_copy(update={"model_name": settings.model_name})
    response = OpenAIResponsesGenerator(client, settings).generate("task-1", request)

    assert response.raw_output == "SELECT 1"
    assert response.provider == "openai"
    assert response.input_tokens == 120
    assert response.cached_input_tokens == 40
    assert responses.kwargs["store"] is False
    assert responses.kwargs["tools"] == []
    assert responses.kwargs["tool_choice"] == "none"
    assert responses.kwargs["reasoning"] == {"effort": "none"}
    assert "api_key" not in responses.kwargs


def test_recording_replays_only_the_exact_request(tmp_path: Path) -> None:
    request = _request().model_copy(update={"model_name": "gpt-5.6-luna"})
    digest = request_sha256("task-1", request)
    path = tmp_path / "recording.json"
    recording = load_recording(path, model_name="gpt-5.6-luna")
    response = GenerationResponse(
        raw_output="SELECT 1",
        model_name="gpt-5.6-luna",
        requested_model_name="gpt-5.6-luna",
        provider="openai",
        endpoint="responses",
        status="completed",
    )
    save_record(
        recording,
        path,
        task_id="task-1",
        digest=digest,
        response=response,
    )

    loaded = load_recording(path, model_name="gpt-5.6-luna")
    replay = recorded_response(loaded, task_id="task-1", expected_request_sha256=digest)
    assert replay and replay.replayed
    with pytest.raises(ValueError, match="digest does not match"):
        recorded_response(loaded, task_id="task-1", expected_request_sha256="0" * 64)


def test_luna_budget_reservation_and_cumulative_ledger(tmp_path: Path) -> None:
    request = _request().model_copy(
        update={"model_name": "gpt-5.6-luna", "max_output_tokens": 1000}
    )
    reservation = maximum_request_cost(request)
    assert Decimal("0") < reservation < Decimal("0.02")

    response = GenerationResponse(
        raw_output="SELECT 1",
        model_name="gpt-5.6-luna",
        requested_model_name="gpt-5.6-luna",
        provider="openai",
        endpoint="responses",
        status="completed",
        input_tokens=1000,
        cached_input_tokens=100,
        output_tokens=100,
    )
    assert response_cost(response) == Decimal("0.00151000")

    config = SpendBudgetConfig(
        project_limit_usd=0.01,
        run_limit_usd=0.01,
        ledger_path=tmp_path / "ledger.json",
    )
    ledger = SpendLedger(config)
    ledger.authorize_run([Decimal("0.005")])
    ledger.record(task_id="task-1", request_digest="a" * 64, cost=response_cost(response))
    assert SpendLedger(config).spent == Decimal("0.00151000")
    with pytest.raises(RuntimeError, match="cumulative project"):
        ledger.authorize_run([Decimal("0.009")])


def test_luna_budget_applies_long_context_multiplier() -> None:
    request = GenerationRequest(
        messages=[PromptMessage(role="user", content="x" * 272_001)],
        model_name="gpt-5.6-luna",
        max_output_tokens=1000,
        prompt_version="fixture-v1",
    )
    assert maximum_request_cost(request) > Decimal("0.55")
