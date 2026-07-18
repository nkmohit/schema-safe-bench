"""Provider-neutral SQL generation contracts."""

from schema_safe_bench.generation.base import Generator, OfflineGenerator
from schema_safe_bench.generation.budget import SpendLedger, maximum_request_cost, response_cost
from schema_safe_bench.generation.openai_responses import OpenAIResponsesGenerator
from schema_safe_bench.generation.recording import (
    load_recording,
    recorded_response,
    request_sha256,
    save_record,
)

__all__ = [
    "Generator",
    "OfflineGenerator",
    "OpenAIResponsesGenerator",
    "SpendLedger",
    "load_recording",
    "maximum_request_cost",
    "recorded_response",
    "request_sha256",
    "response_cost",
    "save_record",
]
