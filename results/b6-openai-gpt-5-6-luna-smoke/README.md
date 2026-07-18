# B6 GPT-5.6 Luna Smoke Result

This directory contains the live B6 bounded-repair smoke artifact for SchemaSafeBench. It is a 20-task pipeline check over the committed BIRD Mini-Dev manifest, not a complete benchmark result.

## Frozen inputs

- Method: `B6`, controlled extension of the committed B4 first pass.
- Reused inputs: all B4 schema packs, generation requests, response recordings, and candidate SQL.
- Eligibility: validator rejection or controlled SQLite error or interruption only.
- Excluded from repair: `ABSTAIN`, successful execution, provider failure, environmental database absence, and all evaluator outcomes.
- Eligible task IDs frozen without repair outcomes: `116` and `1185`.
- Maximum repair attempts: one, stage `repair-1`.
- Repair inputs: public question, unchanged B4 schema pack, rejected candidate, and normalized validator or executor error.
- Model requested and resolved: `gpt-5.6-luna`.
- Temperature: `0.0`; reasoning effort: `none`; maximum output tokens: `1000`.
- API response storage requested: `false`.
- Evaluator policy: `bird-execution-v1`.
- Implementation revision: `52c1232c6b86413f8ea7d7b7daad4246aba70c7f`.

The full run configuration is [`configs/runs/b6-openai-luna-smoke.yaml`](../../configs/runs/b6-openai-luna-smoke.yaml), policy provenance is [`data/provenance/b6-validator-repair.json`](../../data/provenance/b6-validator-repair.json), and the separate repair recording is [`data/processed/predictions/b6-openai-gpt-5-6-luna-repair-smoke.json`](../../data/processed/predictions/b6-openai-gpt-5-6-luna-repair-smoke.json).

## Outcome

| Record | Value |
|---|---:|
| Tasks | 20 |
| Correct | 3 |
| Semantic mismatches | 9 |
| Safe abstentions | 7 |
| Validator rejections | 1 |
| Execution errors or interruptions | 0 |
| Repair-eligible tasks | 2 |
| Repair attempts | 2 |
| First-pass input/output tokens | 6502 / 1098 |
| Repair input/output tokens | 676 / 167 |
| Total input/output tokens | 7178 / 1265 |
| Reused B4 first-pass cost | `$0.013090` |
| Incremental repair cost | `$0.001678` |
| Total B6 token cost | `$0.014768` |

Both repair responses completed. B6 records the same three correct tasks as B4. Task `1185` changes from validator rejection to safe abstention. Task `116` changes from controlled execution interruption to validator rejection. The run therefore has no correctness improvement or regression relative to B4.

## Evidence and interpretation

B6 uses B4's unchanged schema packs, so evaluator-only evidence is identical: full required-table recall on 14 tasks, full required-column recall on 10, and 10 tasks with at least one retrieval miss. The repair stage adds `$0.001678` to the B4 first-pass cost, increases safe abstentions by one, removes the execution interruption, and leaves aggregate correctness unchanged.

These are paired smoke observations, not causal estimates, complete benchmark results, or significance claims. A safer terminal state is not equivalent to a correct answer. The task `116` transition also exposes a validator limitation around the generated CTE alias `f`; it must not be interpreted as successful repair.

See [`failure-analysis.md`](failure-analysis.md), the generated [B4 comparison](../b4-vs-b6-openai-gpt-5-6-luna-smoke/README.md), and the generated [B0 comparison](../b0-vs-b6-openai-gpt-5-6-luna-smoke/README.md).

## Files

- [`trace.jsonl`](trace.jsonl): one audit trace per task with first-pass and optional repair provenance.
- [`trace.summary.json`](trace.summary.json): aggregate outcomes and split first-pass/repair accounting.
- [`failure-analysis.md`](failure-analysis.md): trace-grounded repaired cases and limitations.
