# B4 GPT-5.6 Luna Smoke Result

This directory contains the live B4 hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B4`, deterministic hybrid schema retrieval.
- Retrieval policy: `bm25-bge-rrf-schema-documents-v1`, 12 final document hits.
- Fusion: equal-weight reciprocal-rank fusion over complete BM25 and dense rankings with rank constant 60 and ascending document-ID tie-breaking.
- Lexical component: `rank_bm25.BM25Okapi` with `k1=1.5`, `b=0.75`, and `epsilon=0.25`.
- Dense component: `BAAI/bge-small-en-v1.5` at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
- Embedding runtime: CPU float32, normalized 384-dimensional vectors, batch size 32, one Torch thread, deterministic algorithms enabled.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`, unchanged from B0 through B3.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Schema-evidence policy: evaluator-only `reference-sql-identifiers-v1`.
- Implementation revision: `1dee8779062d14837f930603bda1b93fde9870fd`.

The full run configuration is [`configs/runs/b4-openai-luna-smoke.yaml`](../../configs/runs/b4-openai-luna-smoke.yaml), retrieval provenance is [`data/provenance/b4-hybrid-schema-retrieval.json`](../../data/provenance/b4-hybrid-schema-retrieval.json), and the exact response recording is [`data/processed/predictions/b4-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b4-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 3 |
| Semantic mismatches | 9 |
| Safe abstentions | 6 |
| Validator rejections | 1 |
| Bounded-execution interruptions | 1 |
| Input tokens | 6502 |
| Output tokens | 1098 |
| Estimated token cost | `$0.013090` |
| Total schema characters | 17450 |

All 20 provider responses completed. The run is reported without prompt tuning, fusion changes, or outcome-driven retries. All 240 final hits record their raw BM25 and cosine scores, both component ranks, both reciprocal-rank contributions, fused scores, selected schema objects, embedding provenance and digests, serialized prompt context, request digest, model metadata, usage, cost, validation, execution, and official-compatible comparison.

## Schema evidence

Evaluator-only analysis found full required-table recall on 14 tasks and full required-column recall on 10. Ten tasks missed at least one identifier used by the public reference SQL. Macro table recall was `0.8500`, macro column recall was `0.7731`, macro table precision was `0.5479`, and macro column precision was `0.1806`.

Identifier presence is not a correctness guarantee. Task `1028` had complete evidence but a semantic mismatch. Task `800` had complete evidence and was correct, while task `414` omitted `sets.baseSetSize` and produced a semantic mismatch.

## Interpretation boundary

Against B0, B4 used 54.8% fewer schema characters, 43.9% fewer input tokens, and 32.7% lower estimated token cost, while recording three fewer correct tasks. Against B1, B4 used 1.7% fewer schema characters and 2.3% lower estimated token cost, while recording one fewer correct task. Against B2, B4 used 10.3% more schema characters and 13.5% higher estimated token cost, while recording one additional correct task. Against B3, B4 used 6.3% fewer schema characters and recorded the same number correct, while estimated token cost was 15.9% higher because the recorded output was longer.

These are paired smoke observations, not causal estimates or significance claims. Hosted generation is not bit-for-bit deterministic even with temperature zero. The revision-pinned local embedding path is reproducible only under the documented dependency and CPU execution contract; the response recording is the deterministic hosted replay source. See [`failure-analysis.md`](failure-analysis.md) and the generated [B0 comparison](../b0-vs-b4-openai-gpt-5-6-luna-smoke/README.md), [B1 comparison](../b1-vs-b4-openai-gpt-5-6-luna-smoke/README.md), [B2 comparison](../b2-vs-b4-openai-gpt-5-6-luna-smoke/README.md), and [B3 comparison](../b3-vs-b4-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task, including hybrid retrieval and evaluator-only evidence.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded representative cases and limitations.
