# B1 versus B2 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B1 applies the 1,000-character catalog-prefix policy; B2 applies the locked 12-hit BM25 policy.

| Metric | B1 truncated schema | B2 BM25 | Delta |
|---|---:|---:|---:|
| Correct | 4 | 2 | -2 |
| Accuracy | 20% | 10% | -10 percentage points |
| Safe abstentions | 6 | 10 | +4 |
| Validator rejections | 3 | 2 | -1 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 17757 | 15827 | -1930 |
| Input tokens | 6381 | 6102 | -279 |
| Output tokens | 1169 | 906 | -263 |
| Estimated token cost | `$0.013395` | `$0.011538` | `-$0.001857` |
| Full-table-recall tasks | 15 | 10 | -5 |
| Full-column-recall tasks | 14 | 8 | -6 |
| Retrieval-miss tasks | 6 | 12 | +6 |

B2 improved tasks `1351` and `414`, regressed tasks `24`, `740`, `800`, and `1042`, and left correctness status unchanged on 14 tasks. It used 10.9% fewer schema characters and 13.9% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
