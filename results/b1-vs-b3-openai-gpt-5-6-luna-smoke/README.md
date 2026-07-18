# B1 versus B3 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B1 applies the 1,000-character catalog-prefix policy; B3 applies the locked 12-hit dense-retrieval policy.

| Metric | B1 truncated schema | B3 dense | Delta |
|---|---:|---:|---:|
| Correct | 4 | 3 | -1 |
| Accuracy | 20% | 15% | -5 percentage points |
| Safe abstentions | 6 | 9 | +3 |
| Validator rejections | 3 | 1 | -2 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 17757 | 18633 | +876 |
| Input tokens | 6381 | 6695 | +314 |
| Output tokens | 1169 | 767 | -402 |
| Estimated token cost | `$0.013395` | `$0.011297` | `-$0.002098` |
| Full-table-recall tasks | 15 | 13 | -2 |
| Full-column-recall tasks | 14 | 9 | -5 |
| Retrieval-miss tasks | 6 | 11 | +5 |

B3 improved tasks `1351` and `414`, regressed tasks `24`, `740`, and `800`, and left correctness status unchanged on 15 tasks. It used 4.9% more schema characters and 15.7% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
