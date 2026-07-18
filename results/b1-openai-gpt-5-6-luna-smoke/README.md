# B1 GPT-5.6 Luna Smoke Result

This directory contains the live B1 hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B1`, deterministic length-truncated schema context.
- Truncation policy: `catalog-character-prefix-v1`, maximum 1,000 characters.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`, unchanged from B0.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Implementation revision: `12d81ff81573ebf60a5f43078b2a687e51943839`.

The full run configuration is [`configs/runs/b1-openai-luna-smoke.yaml`](../../configs/runs/b1-openai-luna-smoke.yaml), the truncation provenance is [`data/provenance/b1-schema-truncation.json`](../../data/provenance/b1-schema-truncation.json), and the exact response recording is [`data/processed/predictions/b1-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b1-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 4 |
| Semantic mismatches | 7 |
| Safe abstentions | 6 |
| Validator rejections | 3 |
| Execution errors or interruptions | 0 |
| Input tokens | 6381 |
| Output tokens | 1169 |
| Estimated token cost | `$0.013395` |
| Total schema characters | 17757 |

The result is reported without prompt tuning or outcome-driven retries. All 20 provider responses completed, and both the requested and resolved model identifiers were `gpt-5.6-luna`. The JSONL trace preserves every raw output, extracted SQL, prompt-visible schema pack, validation result, execution result, comparison, request digest, configuration digest, token count, and estimated cost.

## Interpretation boundary

The 1,000-character policy reduced context for 15 tasks and left five task prompts unchanged because their complete schemas already fit. Hosted generation is not bit-for-bit deterministic at temperature zero: task `218` had the same request digest in B0 and B1 but produced a different response and outcome category. The paired artifact is therefore a transparent smoke comparison, not a causal estimate or statistical claim about truncation.

See [`failure-analysis.md`](failure-analysis.md) for representative cases and [`results/b0-vs-b1-openai-gpt-5-6-luna-smoke`](../b0-vs-b1-openai-gpt-5-6-luna-smoke/README.md) for the generated paired comparison.

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded representative cases and limitations.
