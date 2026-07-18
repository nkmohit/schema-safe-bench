# B0 versus B3 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B0 supplies the full schema; B3 applies the locked 12-hit dense-retrieval policy.

| Metric | B0 full schema | B3 dense | Delta |
|---|---:|---:|---:|
| Correct | 6 | 3 | -3 |
| Accuracy | 30% | 15% | -15 percentage points |
| Safe abstentions | 2 | 9 | +7 |
| Validator rejections | 0 | 1 | +1 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 18633 | -20001 |
| Input tokens | 11588 | 6695 | -4893 |
| Output tokens | 1311 | 767 | -544 |
| Estimated token cost | `$0.019454` | `$0.011297` | `-$0.008157` |
| Full-table-recall tasks | 20 | 13 | -7 |
| Full-column-recall tasks | 20 | 9 | -11 |
| Retrieval-miss tasks | 0 | 11 | +11 |

B3 improved task `414`, regressed tasks `24`, `47`, `740`, and `800`, and left correctness status unchanged on 15 tasks. It used 51.8% fewer schema characters and 41.9% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
