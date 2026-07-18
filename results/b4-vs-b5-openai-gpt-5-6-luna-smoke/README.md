# B4 versus B5 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B4 selects the top 12 fused hits; B5 reranks the frozen top-48 B4 candidate set before selecting 12 hits.

| Metric | B4 hybrid | B5 reranked | Delta |
|---|---:|---:|---:|
| Correct | 3 | 2 | -1 |
| Accuracy | 15% | 10% | -5 percentage points |
| Safe abstentions | 6 | 8 | +2 |
| Validator rejections | 1 | 2 | +1 |
| Execution errors or interruptions | 1 | 0 | -1 |
| Schema characters | 17450 | 12985 | -4465 |
| Input tokens | 6502 | 5366 | -1136 |
| Output tokens | 1098 | 784 | -314 |
| Estimated token cost | `$0.013090` | `$0.010070` | `-$0.003020` |
| Full-table-recall tasks | 14 | 11 | -3 |
| Full-column-recall tasks | 10 | 8 | -2 |
| Retrieval-miss tasks | 10 | 12 | +2 |

B5 had no improved tasks, regressed task `800`, and left correctness status unchanged on 19 tasks. It used 25.6% fewer schema characters and 23.1% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
