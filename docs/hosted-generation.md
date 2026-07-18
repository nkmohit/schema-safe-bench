# Hosted Generation and Cost Control

SchemaSafeBench's first hosted path uses OpenAI's Responses API with `gpt-5.6-luna`. The adapter implements the existing provider-neutral generator contract; evaluator, validator, execution, and result-comparison code remain provider independent.

## Locked B0 configuration

The committed smoke configuration is [`configs/runs/b0-openai-luna-smoke.yaml`](../configs/runs/b0-openai-luna-smoke.yaml). It records:

- provider and Responses API endpoint;
- requested model identifier and the model identifier returned by the API;
- prompt version, temperature, reasoning effort, and output-token cap;
- input, cached-input, and output token usage;
- request latency and estimated token cost;
- `store: false`, so the project does not request server-side response storage;
- configuration digest and Git software revision.

The B0 prompt contains only the public question and the database's full schema catalog. Reference SQL and reference results remain evaluator-only.

## Local credential setup

Install the hosted extra and create the ignored environment file:

```bash
uv sync --extra openai --dev
cp .env.example .env
chmod 600 .env
```

Set `OPENAI_API_KEY` only in `.env`. Never commit the file, print the key, place it in a run configuration, or add it to a trace.

## Spend ceiling

The runner enforces a cumulative local ceiling of `$95.00`, below the project's `$100` maximum. It also limits this smoke run to `$5.00`.

Before any missing request is sent, the runner calculates a conservative reservation using UTF-8 prompt bytes plus the configured maximum output tokens. The complete set of missing requests must fit both limits. After every API response, actual token usage is priced and written atomically to the ignored ledger at `.cache/schema-safe-bench/openai-spend.json` before the response recording is updated.

The checked pricing table is specific to `gpt-5.6-luna`: `$1.00` per million input tokens, `$0.10` per million cached-input tokens, and `$6.00` per million output tokens. The guard also applies the published long-context multipliers when input exceeds `272000` tokens. A different model is rejected until its pricing is explicitly added and verified. Local accounting covers calls made by this runner; configure a matching provider-side project budget as an independent safeguard and do not delete the local ledger between hosted runs.

The machine-readable pricing and API provenance is recorded in [`data/provenance/openai-gpt-5.6-luna.json`](../data/provenance/openai-gpt-5.6-luna.json).

## Live generation and deterministic replay

Run the hosted smoke configuration:

```bash
uv run schema-safe-bench run hosted \
  --config configs/runs/b0-openai-luna-smoke.yaml
```

Each successful response is saved atomically to the configured recording. A rerun validates the request digest and reuses that response without making another API call. To require a fully offline path, use a different output path:

```bash
uv run schema-safe-bench run hosted \
  --config configs/runs/b0-openai-luna-smoke.yaml \
  --replay-only \
  --output results/local/b0-luna-replay/trace.jsonl
```

Replay fails if any task is missing or if the question, schema pack, prompt version, model, or generation settings change. This prevents stale responses from being silently evaluated under a different request contract.

## Verified smoke artifact

The committed live run resolves both the requested and returned model identifiers to `gpt-5.6-luna` and links every trace to implementation revision `d9d89a025058c4561e41cca0a711c9082048b05e`.

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 6 |
| Semantic mismatches | 10 |
| Safe abstentions | 2 |
| Bounded-execution interruptions | 2 |
| Input tokens | 11588 |
| Output tokens | 1311 |
| Estimated token cost | `$0.019454` |

The digest-checked replay reproduced the same summary for all 20 tasks without adding a ledger entry. The generated SQL, model metadata, schema packs, validation outcomes, execution outcomes, and official-compatible comparisons are available in [`results/b0-openai-gpt-5-6-luna-smoke`](../results/b0-openai-gpt-5-6-luna-smoke/README.md).

## Limitations

- Token cost is calculated from API-reported usage and the checked Luna price table; it does not include taxes, account credits, or unrelated provider usage.
- An interrupted provider request can still be billable even when no complete response is returned. The margin between the local ceiling and the project maximum is retained for this class of uncertainty.
- Temperature zero and reasoning effort `none` reduce sampling and reasoning cost, but hosted output is not claimed to be bit-for-bit deterministic. The committed recording is the deterministic replay source.
- The current model catalog exposes `gpt-5.6-luna` as the available identifier and the API returned that same identifier; no distinct dated Luna snapshot was available to pin for this run.
- The 20-task run is a smoke baseline, not a complete BIRD benchmark result or a cross-model comparison.
