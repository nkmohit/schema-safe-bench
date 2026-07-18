# Hosted Generation and Cost Control

SchemaSafeBench's first hosted path uses OpenAI's Responses API with `gpt-5.6-luna`. The adapter implements the existing provider-neutral generator contract; evaluator, validator, execution, and result-comparison code remain provider independent.

## Locked B0 through B3 configurations

The committed smoke configurations are [`configs/runs/b0-openai-luna-smoke.yaml`](../configs/runs/b0-openai-luna-smoke.yaml), [`configs/runs/b1-openai-luna-smoke.yaml`](../configs/runs/b1-openai-luna-smoke.yaml), [`configs/runs/b2-openai-luna-smoke.yaml`](../configs/runs/b2-openai-luna-smoke.yaml), and [`configs/runs/b3-openai-luna-smoke.yaml`](../configs/runs/b3-openai-luna-smoke.yaml). They record:

- provider and Responses API endpoint;
- requested model identifier and the model identifier returned by the API;
- prompt version, temperature, reasoning effort, and output-token cap;
- input, cached-input, and output token usage;
- request latency and estimated token cost;
- `store: false`, so the project does not request server-side response storage;
- configuration digest and Git software revision.

The B0 prompt contains only the public question and the database's full schema catalog. B1 changes only the schema context with `catalog-character-prefix-v1`. B2 applies `bm25-schema-documents-v1`, and B3 applies `bge-dense-schema-documents-v1` using a revision-pinned local embedding model. These policies are described in [the experiment protocol](experiment-protocol.md#methods). Reference SQL, reference results, task evidence, and evaluator-derived schema labels remain evaluator-only.

## Local B3 model preparation

Install both optional stacks when preparing a live B3 run, then cache the immutable embedding snapshot:

```bash
uv sync --extra dense --extra openai --dev
uv run schema-safe-bench retrieval cache-model \
  --config configs/runs/b3-openai-luna-smoke.yaml
```

The cache command downloads only the configured model and revision. It verifies the configured dimension, tokenizer ceiling, and committed file digests. The hosted runner uses `local_files_only: true`; it cannot silently refresh the model during retrieval. The ignored cache is `.cache/schema-safe-bench/huggingface` and is not a distributable benchmark artifact.

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

Run a hosted smoke configuration:

```bash
uv run schema-safe-bench run hosted \
  --config configs/runs/b0-openai-luna-smoke.yaml
```

Use the corresponding committed run configuration for B1, B2, or B3. All four methods use the same hosted model, prompt version, sampling settings, output cap, task manifest, validator, executor, and evaluator policy.

Each successful response is saved atomically to the configured recording. A rerun validates the request digest and reuses that response without making another API call. To require a fully offline path, use a different output path:

```bash
uv run schema-safe-bench run hosted \
  --config configs/runs/b0-openai-luna-smoke.yaml \
  --replay-only \
  --output results/local/b0-luna-replay/trace.jsonl
```

Replay fails if any task is missing or if the question, schema pack, prompt version, model, or generation settings change. This prevents stale responses from being silently evaluated under a different request contract.

After a trace is complete, schema evidence can be regenerated without provider dependencies or credentials:

```bash
uv run schema-safe-bench results schema-evidence \
  --trace results/b2-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --tasks data/raw/bird-minidev/mini_dev_sqlite.json \
  --databases data/raw/bird-minidev/dev_databases \
  --output results/schema-evidence-smoke/b2.json
```

The report records the source trace digest and derives required identifiers only inside evaluation. It never modifies the recorded request or response.

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

The committed B1 run links every trace to implementation revision `12d81ff81573ebf60a5f43078b2a687e51943839` and records:

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 4 |
| Semantic mismatches | 7 |
| Safe abstentions | 6 |
| Validator rejections | 3 |
| Input tokens | 6381 |
| Output tokens | 1169 |
| Estimated token cost | `$0.013395` |

The [paired B0-versus-B1 artifact](../results/b0-vs-b1-openai-gpt-5-6-luna-smoke/README.md) is generated from the raw traces. It records lower context, token use, and cost for B1 alongside two correctness regressions and no correctness improvements.

The committed B2 run links every trace to implementation revision `719d6a812cd37c7e6d4e504f3c09c5b0d977be9e` and records:

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 2 |
| Semantic mismatches | 6 |
| Safe abstentions | 10 |
| Validator rejections | 2 |
| Input tokens | 6102 |
| Output tokens | 906 |
| Estimated token cost | `$0.011538` |

The B2 trace records all 240 ranked retrieval hits and evaluator-only schema evidence. The [B0-versus-B2](../results/b0-vs-b2-openai-gpt-5-6-luna-smoke/README.md) and [B1-versus-B2](../results/b1-vs-b2-openai-gpt-5-6-luna-smoke/README.md) artifacts preserve paired outcomes, context, evidence, token use, cost, and interpretation limits.

The committed B3 run links every trace to implementation revision `59677d0d897198b10cf728d49e7a45a7c88173b3` and records:

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 3 |
| Semantic mismatches | 7 |
| Safe abstentions | 9 |
| Validator rejections | 1 |
| Input tokens | 6695 |
| Output tokens | 767 |
| Estimated token cost | `$0.011297` |

Every B3 trace preserves its 12 ranked dense hits, cosine scores, selected identifiers, embedding model and revision, document and query embedding digests, serialized schema pack, request digest, generation metadata, and evaluator outcomes. The [B0-versus-B3](../results/b0-vs-b3-openai-gpt-5-6-luna-smoke/README.md), [B1-versus-B3](../results/b1-vs-b3-openai-gpt-5-6-luna-smoke/README.md), and [B2-versus-B3](../results/b2-vs-b3-openai-gpt-5-6-luna-smoke/README.md) artifacts preserve the paired descriptive results.

## Limitations

- Token cost is calculated from API-reported usage and the checked Luna price table; it does not include taxes, account credits, or unrelated provider usage.
- An interrupted provider request can still be billable even when no complete response is returned. The margin between the local ceiling and the project maximum is retained for this class of uncertainty.
- Temperature zero and reasoning effort `none` reduce sampling and reasoning cost, but hosted output is not claimed to be bit-for-bit deterministic. The committed recording is the deterministic replay source.
- The current model catalog exposes `gpt-5.6-luna` as the available identifier and the API returned that same identifier; no distinct dated Luna snapshot was available to pin for this run.
- The local B3 embedding snapshot is revision-pinned and digest-checked, but exact floating-point reproducibility is guaranteed only for the documented CPU, dependency, precision, and thread settings.
- The 20-task run is a smoke baseline, not a complete BIRD benchmark result or a cross-model comparison.
