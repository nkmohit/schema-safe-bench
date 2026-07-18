"""Prompts that expose schema evidence but never evaluation references."""

import re
from typing import Literal

from schema_safe_bench.models import GenerationRequest, PromptMessage, SchemaPack

PROMPT_VERSION = "sqlite-readonly-v1"

_SYSTEM = """You generate SQLite for a controlled public benchmark.
Return exactly one SELECT statement or one read-only WITH ... SELECT statement.
Use only identifiers present in the supplied schema.
Return ABSTAIN when the question cannot be grounded safely.
Do not include markdown, explanation, comments, PRAGMA, DDL, DML, or multiple statements."""


def build_generation_request(
    *,
    question: str,
    schema_pack: SchemaPack,
    model_name: str,
    temperature: float = 0.0,
    max_output_tokens: int = 1000,
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none",
) -> GenerationRequest:
    user = f"Question:\n{question}\n\nAvailable schema:\n{schema_pack.serialized}"
    return GenerationRequest(
        messages=[
            PromptMessage(role="system", content=_SYSTEM),
            PromptMessage(role="user", content=user),
        ],
        model_name=model_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        prompt_version=PROMPT_VERSION,
        reasoning_effort=reasoning_effort,
    )


def build_repair_request(
    *,
    question: str,
    schema_pack: SchemaPack,
    rejected_sql: str,
    error: str,
    model_name: str,
    temperature: float = 0.0,
    max_output_tokens: int = 1000,
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none",
) -> GenerationRequest:
    user = (
        f"Question:\n{question}\n\nAvailable schema:\n{schema_pack.serialized}"
        f"\n\nRejected candidate:\n{rejected_sql}\n\nValidation or execution error:\n{error}"
        "\n\nReturn one corrected read-only query or ABSTAIN."
    )
    return GenerationRequest(
        messages=[
            PromptMessage(role="system", content=_SYSTEM),
            PromptMessage(role="user", content=user),
        ],
        model_name=model_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        prompt_version=f"{PROMPT_VERSION}-repair-1",
        reasoning_effort=reasoning_effort,
    )


def extract_candidate_sql(raw_output: str) -> str:
    """Remove one optional Markdown fence while preserving the raw response separately."""
    stripped = raw_output.strip()
    if stripped.upper() == "ABSTAIN":
        return "ABSTAIN"
    match = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else stripped
