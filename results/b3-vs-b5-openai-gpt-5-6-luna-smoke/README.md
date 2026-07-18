# B3 versus B5 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B3 applies the locked 12-hit dense policy; B5 applies unchanged B4 fusion and then local reranking.

| Metric | B3 dense | B5 reranked | Delta |
|---|---:|---:|---:|
| Correct | 3 | 2 | -1 |
| Accuracy | 15% | 10% | -5 percentage points |
| Safe abstentions | 9 | 8 | -1 |
| Validator rejections | 1 | 2 | +1 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 18633 | 12985 | -5648 |
| Input tokens | 6695 | 5366 | -1329 |
| Output tokens | 767 | 784 | +17 |
| Estimated token cost | `$0.011297` | `$0.010070` | `-$0.001227` |
| Full-table-recall tasks | 13 | 11 | -2 |
| Full-column-recall tasks | 9 | 8 | -1 |
| Retrieval-miss tasks | 11 | 12 | +1 |

B5 had no improved tasks, regressed task `414`, and left correctness status unchanged on 19 tasks. It used 30.3% fewer schema characters and 10.9% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
