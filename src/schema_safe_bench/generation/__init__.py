"""Provider-neutral SQL generation contracts."""

from schema_safe_bench.generation.base import Generator, OfflineGenerator
from schema_safe_bench.generation.budget import SpendLedger, maximum_request_cost, response_cost
from schema_safe_bench.generation.openai_responses import OpenAIResponsesGenerator
from schema_safe_bench.generation.recording import (
    load_recording,
    load_recording_with_sources,
    load_repair_recording,
    load_repair_recording_with_sources,
    recorded_repair_response,
    recorded_response,
    repair_request_sha256,
    request_sha256,
    save_record,
    save_repair_record,
)

__all__ = [
    "Generator",
    "OfflineGenerator",
    "OpenAIResponsesGenerator",
    "SpendLedger",
    "load_recording",
    "load_recording_with_sources",
    "load_repair_recording",
    "load_repair_recording_with_sources",
    "maximum_request_cost",
    "recorded_repair_response",
    "recorded_response",
    "repair_request_sha256",
    "request_sha256",
    "response_cost",
    "save_record",
    "save_repair_record",
]
