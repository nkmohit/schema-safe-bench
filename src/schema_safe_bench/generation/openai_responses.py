"""OpenAI Responses API adapter with no credential persistence."""

import os
from time import perf_counter
from typing import Any, Protocol

from schema_safe_bench.models import GenerationRequest, GenerationResponse, HostedModelConfig


class _ResponsesResource(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _OpenAIClient(Protocol):
    responses: _ResponsesResource


class OpenAIResponsesGenerator:
    """Generate SQL through the Responses API while keeping requests stateless."""

    def __init__(self, client: _OpenAIClient, settings: HostedModelConfig) -> None:
        self.client = client
        self.settings = settings

    @classmethod
    def from_environment(cls, settings: HostedModelConfig) -> "OpenAIResponsesGenerator":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "OpenAI support is not installed; run `uv sync --extra openai --dev`"
            ) from exc
        client = OpenAI(
            api_key=api_key,
            max_retries=settings.max_retries,
            timeout=settings.timeout_seconds,
        )
        return cls(client, settings)

    def generate(self, task_id: str, request: GenerationRequest) -> GenerationResponse:
        del task_id
        if request.model_name != self.settings.model_name:
            raise ValueError("request model does not match the configured hosted model")
        instructions = "\n\n".join(
            message.content for message in request.messages if message.role == "system"
        )
        inputs = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role != "system"
        ]
        started = perf_counter()
        response = self.client.responses.create(
            model=request.model_name,
            instructions=instructions,
            input=inputs,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            reasoning={"effort": request.reasoning_effort},
            store=False,
            tools=[],
            tool_choice="none",
        )
        elapsed_ms = (perf_counter() - started) * 1000
        usage = getattr(response, "usage", None)
        input_details = getattr(usage, "input_tokens_details", None)
        status = getattr(response, "status", None) or "failed"
        if status not in {"completed", "incomplete", "failed"}:
            status = "failed"
        return GenerationResponse(
            raw_output=getattr(response, "output_text", "") or "",
            model_name=getattr(response, "model", request.model_name),
            requested_model_name=request.model_name,
            provider="openai",
            endpoint="responses",
            status=status,
            input_tokens=getattr(usage, "input_tokens", None),
            cached_input_tokens=getattr(input_details, "cached_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            request_elapsed_ms=elapsed_ms,
        )
