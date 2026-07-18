# B2 versus B5 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B2 applies the locked 12-hit BM25 policy; B5 reranks a fixed B4 candidate set before selecting 12 hits.

| Metric | B2 BM25 | B5 reranked | Delta |
|---|---:|---:|---:|
| Correct | 2 | 2 | 0 |
| Accuracy | 10% | 10% | 0 percentage points |
| Safe abstentions | 10 | 8 | -2 |
| Validator rejections | 2 | 2 | 0 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 15827 | 12985 | -2842 |
| Input tokens | 6102 | 5366 | -736 |
| Output tokens | 906 | 784 | -122 |
| Estimated token cost | `$0.011538` | `$0.010070` | `-$0.001468` |
| Full-table-recall tasks | 10 | 11 | +1 |
| Full-column-recall tasks | 8 | 8 | 0 |
| Retrieval-miss tasks | 12 | 12 | 0 |

B5 improved task `1042`, regressed task `414`, and left correctness status unchanged on 18 tasks. It used 18.0% fewer schema characters and 12.7% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
