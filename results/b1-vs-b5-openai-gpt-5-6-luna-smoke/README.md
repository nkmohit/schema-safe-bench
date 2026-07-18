# B1 versus B5 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B1 uses the locked catalog-prefix policy; B5 selects 12 documents after local reranking.

| Metric | B1 truncated | B5 reranked | Delta |
|---|---:|---:|---:|
| Correct | 4 | 2 | -2 |
| Accuracy | 20% | 10% | -10 percentage points |
| Safe abstentions | 6 | 8 | +2 |
| Validator rejections | 3 | 2 | -1 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 17757 | 12985 | -4772 |
| Input tokens | 6381 | 5366 | -1015 |
| Output tokens | 1169 | 784 | -385 |
| Estimated token cost | `$0.013395` | `$0.010070` | `-$0.003325` |
| Full-table-recall tasks | 15 | 11 | -4 |
| Full-column-recall tasks | 14 | 8 | -6 |
| Retrieval-miss tasks | 6 | 12 | +6 |

B5 improved task `1351`, regressed tasks `24`, `740`, and `800`, and left correctness status unchanged on 16 tasks. It used 26.9% fewer schema characters and 24.8% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
