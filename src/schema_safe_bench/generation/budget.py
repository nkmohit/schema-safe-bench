"""Local cumulative spend guard for hosted benchmark calls."""

import json
from decimal import Decimal

from schema_safe_bench.models import GenerationRequest, GenerationResponse, SpendBudgetConfig

_MILLION = Decimal(1_000_000)
_LUNA_INPUT_PER_MILLION = Decimal("1.00")
_LUNA_CACHED_INPUT_PER_MILLION = Decimal("0.10")
_LUNA_OUTPUT_PER_MILLION = Decimal("6.00")
_LONG_CONTEXT_THRESHOLD = 272_000


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"))


def maximum_request_cost(request: GenerationRequest) -> Decimal:
    """Return a conservative request ceiling using UTF-8 bytes as a token upper bound."""
    if request.model_name != "gpt-5.6-luna":
        raise ValueError("no verified price table is configured for this model")
    prompt_bytes = sum(len(message.content.encode("utf-8")) for message in request.messages)
    input_token_ceiling = prompt_bytes + 4096
    input_multiplier = Decimal("2") if input_token_ceiling > _LONG_CONTEXT_THRESHOLD else 1
    output_multiplier = Decimal("1.5") if input_token_ceiling > _LONG_CONTEXT_THRESHOLD else 1
    return _money(
        Decimal(input_token_ceiling) * _LUNA_INPUT_PER_MILLION * input_multiplier / _MILLION
        + Decimal(request.max_output_tokens)
        * _LUNA_OUTPUT_PER_MILLION
        * output_multiplier
        / _MILLION
    )


def response_cost(response: GenerationResponse) -> Decimal:
    if response.requested_model_name != "gpt-5.6-luna":
        raise ValueError("no verified price table is configured for this model")
    input_tokens = response.input_tokens or 0
    cached_tokens = response.cached_input_tokens or 0
    output_tokens = response.output_tokens or 0
    if cached_tokens > input_tokens:
        raise ValueError("cached input tokens cannot exceed total input tokens")
    uncached_tokens = input_tokens - cached_tokens
    input_multiplier = Decimal("2") if input_tokens > _LONG_CONTEXT_THRESHOLD else 1
    output_multiplier = Decimal("1.5") if input_tokens > _LONG_CONTEXT_THRESHOLD else 1
    return _money(
        Decimal(uncached_tokens) * _LUNA_INPUT_PER_MILLION * input_multiplier / _MILLION
        + Decimal(cached_tokens) * _LUNA_CACHED_INPUT_PER_MILLION * input_multiplier / _MILLION
        + Decimal(output_tokens) * _LUNA_OUTPUT_PER_MILLION * output_multiplier / _MILLION
    )


class SpendLedger:
    def __init__(self, config: SpendBudgetConfig) -> None:
        self.config = config
        self.spent = Decimal("0")
        self.entries: list[dict[str, str]] = []
        if config.ledger_path.exists():
            payload = json.loads(config.ledger_path.read_text(encoding="utf-8"))
            self.spent = Decimal(str(payload["spent_usd"]))
            self.entries = list(payload.get("entries", []))
            recorded_limit = Decimal(str(payload["project_limit_usd"]))
            if Decimal(str(config.project_limit_usd)) > recorded_limit:
                raise ValueError(
                    "the configured project limit cannot raise the existing ledger limit"
                )

    def authorize_run(self, reservations: list[Decimal]) -> None:
        reserved = sum(reservations, Decimal("0"))
        if reserved > Decimal(str(self.config.run_limit_usd)):
            raise RuntimeError("hosted run exceeds its configured spend limit")
        if self.spent + reserved > Decimal(str(self.config.project_limit_usd)):
            raise RuntimeError("hosted run could exceed the cumulative project spend limit")

    def record(self, *, task_id: str, request_digest: str, cost: Decimal) -> None:
        if self.spent + cost > Decimal(str(self.config.project_limit_usd)):
            raise RuntimeError("response cost exceeds the cumulative project spend limit")
        self.spent = _money(self.spent + cost)
        self.entries.append(
            {"task_id": task_id, "request_sha256": request_digest, "cost_usd": str(cost)}
        )
        payload = {
            "format_version": "1",
            "project_limit_usd": self.config.project_limit_usd,
            "spent_usd": str(self.spent),
            "entries": self.entries,
        }
        path = self.config.ledger_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
