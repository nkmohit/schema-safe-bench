# B0 GPT-5.6 Luna Smoke Result

This directory contains the first live hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B0`, full schema in the prompt.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Implementation revision: `d9d89a025058c4561e41cca0a711c9082048b05e`.

The full run configuration is [`configs/runs/b0-openai-luna-smoke.yaml`](../../configs/runs/b0-openai-luna-smoke.yaml), and the exact response recording is [`data/processed/predictions/b0-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b0-openai-gpt-5-6-luna-smoke.json).

## Outcome

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

The result is deliberately reported without prompt tuning or outcome-driven retries. The JSONL trace preserves each raw output, extracted SQL, full schema pack, validation result, execution result, comparison, request digest, configuration digest, resolved model, token usage, and estimated cost.

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.

A digest-checked replay of all 20 recorded responses produced an identical summary without making hosted API calls or adding spend-ledger entries.
