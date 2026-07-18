# B2 GPT-5.6 Luna Smoke Result

This directory contains the live B2 hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B2`, deterministic BM25 schema retrieval.
- Retrieval policy: `bm25-schema-documents-v1`, 12 document hits.
- BM25 settings: `k1=1.5`, `b=0.75`, `epsilon=0.25`.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`, unchanged from B0 and B1.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Schema-evidence policy: evaluator-only `reference-sql-identifiers-v1`.
- Implementation revision: `719d6a812cd37c7e6d4e504f3c09c5b0d977be9e`.

The full run configuration is [`configs/runs/b2-openai-luna-smoke.yaml`](../../configs/runs/b2-openai-luna-smoke.yaml), retrieval provenance is [`data/provenance/b2-bm25-schema-retrieval.json`](../../data/provenance/b2-bm25-schema-retrieval.json), and the exact response recording is [`data/processed/predictions/b2-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b2-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 2 |
| Semantic mismatches | 6 |
| Safe abstentions | 10 |
| Validator rejections | 2 |
| Execution errors or interruptions | 0 |
| Input tokens | 6102 |
| Output tokens | 906 |
| Estimated token cost | `$0.011538` |
| Total schema characters | 15827 |

All 20 provider responses completed. The run is reported without prompt tuning or outcome-driven retries. Every trace records its 12 ranked document hits, BM25 score and rank, selected schema objects, serialized prompt context, request digest, model metadata, usage, cost, validation, execution, and official-compatible comparison.

## Schema evidence

Evaluator-only analysis found full required-table recall on 10 tasks and full required-column recall on 8. Twelve tasks missed at least one identifier used by the public reference SQL. Macro table recall was `0.75`, macro column recall was `0.7256`, macro table precision was `0.5092`, and macro column precision was `0.1869`.

These measurements describe identifier presence in the recorded prompt context. They do not prove that a retrieval miss caused an outcome or that full identifier recall guarantees correct SQL. Task `1028` had complete evidence but a semantic mismatch; task `24` missed `satscores` and safely abstained.

## Interpretation boundary

Against B0, B2 used 59.0% fewer schema characters, 47.3% fewer input tokens, and 40.7% lower estimated token cost, while recording four fewer correct tasks. Against B1, it used 10.9% fewer schema characters, 4.4% fewer input tokens, and 13.9% lower estimated token cost, while recording two fewer correct tasks. These are paired smoke observations, not causal estimates or significance claims.

Hosted generation is not bit-for-bit deterministic even with temperature zero. The response recording is the reproducible source for offline replay. See [`failure-analysis.md`](failure-analysis.md) and the generated [B0 comparison](../b0-vs-b2-openai-gpt-5-6-luna-smoke/README.md) and [B1 comparison](../b1-vs-b2-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task, including retrieval hits and evaluator-only evidence.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded representative cases and limitations.
