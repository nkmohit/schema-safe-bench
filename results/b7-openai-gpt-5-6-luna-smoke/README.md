# B7 GPT-5.6 Luna Smoke Result

This directory contains the B7 deterministic-abstention smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B7`, controlled extension of the committed B4 first pass.
- Reused inputs: every B4 schema pack, request, Luna response, request digest, and candidate SQL.
- Original model `ABSTAIN` outputs remain unchanged.
- Enforced abstention: validator rejection or controlled SQLite error or interruption only.
- Successful execution, provider failure, environmental database absence, and evaluator outcomes cannot trigger abstention.
- Enforced task IDs frozen before result publication: `116` and `1185`.
- Model requested and resolved by the reused recording: `gpt-5.6-luna`.
- Evaluator policy: `bird-execution-v1`.
- Implementation revision: `9061bf3e77d8cf9239fed2f76298f41e963c767a`.

The full run configuration is [`configs/runs/b7-openai-luna-smoke.yaml`](../../configs/runs/b7-openai-luna-smoke.yaml), policy provenance is [`data/provenance/b7-validator-abstention.json`](../../data/provenance/b7-validator-abstention.json), and the exact hosted replay source remains the committed [B4 recording](../../data/processed/predictions/b4-openai-gpt-5-6-luna-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 3 |
| Semantic mismatches | 9 |
| Total abstentions | 8 |
| Model abstentions | 6 |
| Enforced abstentions | 2 |
| Validator rejections | 0 |
| Execution errors or interruptions | 0 |
| Abstention coverage | 40% |
| Eligible unsafe terminals | 2 |
| Unsafe-terminal avoidance rate | 100% |
| Reused first-pass input/output tokens | 6502 / 1098 |
| New hosted requests | 0 |
| Incremental token cost | `$0.000000` |
| Total treatment token cost | `$0.013090` |

B7 records the same three correct tasks as B4. Task `116` changes from controlled execution interruption to enforced abstention, and task `1185` changes from validator rejection to enforced abstention. No correctness outcome improves or regresses relative to B4.

## Metric boundary

Coverage counts all terminal abstentions. The unsafe-terminal avoidance rate applies only to the two deterministic policy-eligible cases and is 100% by construction because both were converted to `ABSTAIN`. It is not an accuracy metric. Overall abstention precision is not identifiable for the six model-produced abstentions because no counterfactual SQL exists for them.

Evaluator-only schema evidence is identical to B4: full required-table recall on 14 tasks, full required-column recall on 10, and 10 tasks with at least one retrieval miss. This evidence was unavailable to the abstention decision.

These are paired smoke observations, not causal estimates, complete benchmark results, or significance claims. See [`failure-analysis.md`](failure-analysis.md), the [B4 comparison](../b4-vs-b7-openai-gpt-5-6-luna-smoke/README.md), and the [B0 context comparison](../b0-vs-b7-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task with first-pass and terminal-decision provenance.
- [`trace.summary.json`](trace.summary.json): aggregate outcomes, abstention metrics, and split accounting.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded enforced and model abstention cases.
