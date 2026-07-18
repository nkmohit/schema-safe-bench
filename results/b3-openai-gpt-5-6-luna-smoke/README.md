# B3 GPT-5.6 Luna Smoke Result

This directory contains the live B3 hosted-generation smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B3`, revision-pinned local dense schema retrieval.
- Retrieval policy: `bge-dense-schema-documents-v1`, 12 document hits ranked by cosine similarity with ascending document-ID tie-breaking.
- Embedding model: `BAAI/bge-small-en-v1.5` at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
- Embedding runtime: CPU float32, normalized 384-dimensional vectors, batch size 32, one Torch thread, deterministic algorithms enabled.
- Model requested and resolved: `gpt-5.6-luna`.
- Prompt: `sqlite-readonly-v1`, unchanged from B0 through B2.
- Temperature: `0.0`.
- Reasoning effort: `none`.
- Maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Schema-evidence policy: evaluator-only `reference-sql-identifiers-v1`.
- Implementation revision: `59677d0d897198b10cf728d49e7a45a7c88173b3`.

The full run configuration is [`configs/runs/b3-openai-luna-smoke.yaml`](../../configs/runs/b3-openai-luna-smoke.yaml), retrieval provenance is [`data/provenance/b3-dense-schema-retrieval.json`](../../data/provenance/b3-dense-schema-retrieval.json), and the exact response recording is [`data/processed/predictions/b3-openai-gpt-5-6-luna-smoke.json`](../../data/processed/predictions/b3-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 3 |
| Semantic mismatches | 7 |
| Safe abstentions | 9 |
| Validator rejections | 1 |
| Execution errors or interruptions | 0 |
| Input tokens | 6695 |
| Output tokens | 767 |
| Estimated token cost | `$0.011297` |
| Total schema characters | 18633 |

All 20 provider responses completed. The run is reported without prompt tuning or outcome-driven retries. Every trace records 12 ranked document hits, cosine scores and ranks, selected schema objects, embedding and runtime provenance, vector digests, serialized prompt context, request digest, model metadata, usage, cost, validation, execution, and official-compatible comparison.

## Schema evidence

Evaluator-only analysis found full required-table recall on 13 tasks and full required-column recall on 9. Eleven tasks missed at least one identifier used by the public reference SQL. Macro table recall was `0.8083`, macro column recall was `0.7413`, macro table precision was `0.5667`, and macro column precision was `0.1627`.

Identifier presence is not a correctness guarantee. Task `1028` had complete evidence but a semantic mismatch, while task `414` was execution-equivalent despite incomplete evidence relative to the public reference query.

## Interpretation boundary

Against B0, B3 used 51.8% fewer schema characters, 42.2% fewer input tokens, and 41.9% lower estimated token cost, while recording three fewer correct tasks. Against B1, B3 used 4.9% more schema characters and 4.9% more input tokens, but 15.7% lower estimated token cost and recorded one fewer correct task. Against B2, B3 used 17.7% more schema characters and 9.7% more input tokens, with 2.1% lower estimated token cost and one additional correct task.

These are paired smoke observations, not causal estimates or significance claims. Hosted generation is not bit-for-bit deterministic even with temperature zero. The revision-pinned local embedding path is reproducible only under the documented dependency and CPU execution contract; the response recording is the deterministic hosted replay source. See [`failure-analysis.md`](failure-analysis.md) and the generated [B0 comparison](../b0-vs-b3-openai-gpt-5-6-luna-smoke/README.md), [B1 comparison](../b1-vs-b3-openai-gpt-5-6-luna-smoke/README.md), and [B2 comparison](../b2-vs-b3-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task, including dense retrieval and evaluator-only evidence.
- [`trace.summary.json`](trace.summary.json): aggregate smoke summary.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded representative cases and limitations.
