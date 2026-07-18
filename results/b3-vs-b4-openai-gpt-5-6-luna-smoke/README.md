# B3 versus B4 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B3 applies the locked 12-hit dense policy; B4 fuses complete B2 and B3 rankings before selecting 12 hits.

| Metric | B3 dense | B4 hybrid | Delta |
|---|---:|---:|---:|
| Correct | 3 | 3 | 0 |
| Accuracy | 15% | 15% | 0 percentage points |
| Safe abstentions | 9 | 6 | -3 |
| Validator rejections | 1 | 1 | 0 |
| Execution errors or interruptions | 0 | 1 | +1 |
| Schema characters | 18633 | 17450 | -1183 |
| Input tokens | 6695 | 6502 | -193 |
| Output tokens | 767 | 1098 | +331 |
| Estimated token cost | `$0.011297` | `$0.013090` | `+$0.001793` |
| Full-table-recall tasks | 13 | 14 | +1 |
| Full-column-recall tasks | 9 | 10 | +1 |
| Retrieval-miss tasks | 11 | 10 | -1 |

B4 improved task `800`, regressed task `414`, and left correctness status unchanged on 18 tasks. It used 6.3% fewer schema characters, while estimated token cost was 15.9% higher because the recorded output was longer.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
