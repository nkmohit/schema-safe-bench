# B0 versus B2 GPT-5.6 Luna Smoke Comparison

This paired comparison uses identical task IDs, `gpt-5.6-luna`, prompt version `sqlite-readonly-v1`, temperature `0.0`, reasoning effort `none`, safety controls, and official-compatible evaluation. B0 exposes the full catalog; B2 exposes the pack produced by the locked 12-hit BM25 policy.

| Metric | B0 full schema | B2 BM25 | Delta |
|---|---:|---:|---:|
| Correct | 6 | 2 | -4 |
| Accuracy | 30% | 10% | -20 percentage points |
| Safe abstentions | 2 | 10 | +8 |
| Validator rejections | 0 | 2 | +2 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 15827 | -22807 |
| Input tokens | 11588 | 6102 | -5486 |
| Output tokens | 1311 | 906 | -405 |
| Estimated token cost | `$0.019454` | `$0.011538` | `-$0.007916` |
| Full-table-recall tasks | 20 | 10 | -10 |
| Full-column-recall tasks | 20 | 8 | -12 |
| Retrieval-miss tasks | 0 | 12 | +12 |

B2 improved task `414`, regressed tasks `24`, `47`, `740`, `800`, and `1042`, and left correctness status unchanged on 14 tasks. Its aggregate schema context fell by 59.0% and estimated token cost by 40.7%.

The machine-readable [`comparison.json`](comparison.json) contains paired outcomes, failure categories, schema-character counts, token usage, cost, configuration digests, software revisions, and evaluator-only schema-evidence aggregates. This smoke comparison does not establish causality or statistical significance. Hosted nondeterminism remains part of the observed comparison.
