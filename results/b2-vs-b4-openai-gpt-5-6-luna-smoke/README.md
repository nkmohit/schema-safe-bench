# B2 versus B4 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B2 applies the locked 12-hit BM25 policy; B4 fuses complete B2 and B3 rankings before selecting 12 hits.

| Metric | B2 BM25 | B4 hybrid | Delta |
|---|---:|---:|---:|
| Correct | 2 | 3 | +1 |
| Accuracy | 10% | 15% | +5 percentage points |
| Safe abstentions | 10 | 6 | -4 |
| Validator rejections | 2 | 1 | -1 |
| Execution errors or interruptions | 0 | 1 | +1 |
| Schema characters | 15827 | 17450 | +1623 |
| Input tokens | 6102 | 6502 | +400 |
| Output tokens | 906 | 1098 | +192 |
| Estimated token cost | `$0.011538` | `$0.013090` | `+$0.001552` |
| Full-table-recall tasks | 10 | 14 | +4 |
| Full-column-recall tasks | 8 | 10 | +2 |
| Retrieval-miss tasks | 12 | 10 | -2 |

B4 improved tasks `1042` and `800`, regressed task `414`, and left correctness status unchanged on 17 tasks. It used 10.3% more schema characters and 13.5% higher estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
