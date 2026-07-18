# B5 GPT-5.6 Luna Smoke Result

This directory contains the live B5 hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B5`, deterministic B4 hybrid retrieval followed by local cross-encoder reranking.
- Retrieval policy: `bm25-bge-rrf-minilm-rerank-schema-documents-v1`.
- First stage: unchanged B4 equal-weight reciprocal-rank fusion over complete BM25 and dense rankings, with rank constant 60.
- Reranker candidate depth: 48, limited by the number of schema documents.
- Reranker: `cross-encoder/ms-marco-MiniLM-L6-v2` at revision `c5ee24cb16019beea0893ab7796b1df96625c6b8`.
- Reranker contract: public-question/schema-document pairs, 512-token `longest_first` truncation, raw logits, no threshold, and stable score/pre-rank/document-ID ordering.
- Local inference: CPU float32, batch size 32, one Torch thread, deterministic algorithms enabled.
- Final schema selection: 12 hits.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`, unchanged from B0 through B4.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Schema-evidence policy: evaluator-only `reference-sql-identifiers-v1`.
- Implementation revision: `793b615134274d3f2b782920065a6bf192396b28`.

The full run configuration is [`configs/runs/b5-openai-luna-smoke.yaml`](../../configs/runs/b5-openai-luna-smoke.yaml), reranker provenance is [`data/provenance/b5-hybrid-reranking.json`](../../data/provenance/b5-hybrid-reranking.json), and the exact response recording is [`data/processed/predictions/b5-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b5-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 2 |
| Semantic mismatches | 8 |
| Safe abstentions | 8 |
| Validator rejections | 2 |
| Execution errors or interruptions | 0 |
| Input tokens | 5366 |
| Output tokens | 784 |
| Estimated token cost | `$0.010070` |
| Total schema characters | 12985 |

All 20 provider responses completed. The run is reported without prompt tuning, reranker changes, candidate-depth changes, post-result thresholds, or outcome-driven retries. The traces retain 847 reranked candidates and 240 selected hits. Every candidate records its B4 fused score and pre-rank, raw BM25 and cosine scores, component ranks, reciprocal-rank contributions, raw reranker logit, post-rank, and selected status.

## Schema evidence

Evaluator-only analysis found full required-table recall on 11 tasks and full required-column recall on 8. Twelve tasks missed at least one identifier used by the public reference SQL. Macro table recall was `0.7708`, macro column recall was `0.7108`, macro table precision was `0.6833`, and macro column precision was `0.1977`.

Identifier presence is not a correctness guarantee. Tasks `1042` and `1351` had complete evidence and were correct. Tasks `244`, `226`, `898`, and `1389` had complete evidence but semantic mismatches, while task `218` had complete evidence and was rejected by validation.

## Interpretation boundary

Against B0, B5 used 66.4% fewer schema characters, 53.7% fewer input tokens, and 48.2% lower estimated token cost, while recording four fewer correct tasks. Against B1, B5 used 26.9% fewer schema characters and 24.8% lower estimated token cost, while recording two fewer correct tasks. Against B2, B5 used 18.0% fewer schema characters and 12.7% lower estimated token cost with the same number of correct tasks. Against B3, B5 used 30.3% fewer schema characters and 10.9% lower estimated token cost, while recording one fewer correct task. Against B4, B5 used 25.6% fewer schema characters and 23.1% lower estimated token cost, while recording one fewer correct task.

These are paired smoke observations, not causal estimates, complete benchmark results, or significance claims. Hosted generation is not bit-for-bit deterministic even with temperature zero. The pinned local model paths are reproducible only under the documented dependency, CPU, precision, and thread settings; small numerical differences can reorder near-tied scores. The committed response recording is the deterministic hosted replay source.

See [`failure-analysis.md`](failure-analysis.md) and the generated [B0 comparison](../b0-vs-b5-openai-gpt-5-6-luna-smoke/README.md), [B1 comparison](../b1-vs-b5-openai-gpt-5-6-luna-smoke/README.md), [B2 comparison](../b2-vs-b5-openai-gpt-5-6-luna-smoke/README.md), [B3 comparison](../b3-vs-b5-openai-gpt-5-6-luna-smoke/README.md), and [B4 comparison](../b4-vs-b5-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task, including all reranking candidates and evaluator-only evidence.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded representative cases and limitations.
