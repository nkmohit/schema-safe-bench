# B2 versus B3 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B2 applies the locked 12-hit BM25 policy; B3 applies the locked 12-hit dense-retrieval policy.

| Metric | B2 BM25 | B3 dense | Delta |
|---|---:|---:|---:|
| Correct | 2 | 3 | +1 |
| Accuracy | 10% | 15% | +5 percentage points |
| Safe abstentions | 10 | 9 | -1 |
| Validator rejections | 2 | 1 | -1 |
| Execution errors or interruptions | 0 | 0 | 0 |
| Schema characters | 15827 | 18633 | +2806 |
| Input tokens | 6102 | 6695 | +593 |
| Output tokens | 906 | 767 | -139 |
| Estimated token cost | `$0.011538` | `$0.011297` | `-$0.000241` |
| Full-table-recall tasks | 10 | 13 | +3 |
| Full-column-recall tasks | 8 | 9 | +1 |
| Retrieval-miss tasks | 12 | 11 | -1 |

B3 improved task `1042`, recorded no correctness regressions, and left correctness status unchanged on 19 tasks. It used 17.7% more schema characters, while estimated token cost was 2.1% lower because the recorded output was shorter.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
