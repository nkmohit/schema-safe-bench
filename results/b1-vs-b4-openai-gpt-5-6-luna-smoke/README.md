# B1 versus B4 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B1 applies the 1,000-character catalog-prefix policy; B4 applies the locked 12-hit hybrid fusion policy.

| Metric | B1 truncated schema | B4 hybrid | Delta |
|---|---:|---:|---:|
| Correct | 4 | 3 | -1 |
| Accuracy | 20% | 15% | -5 percentage points |
| Safe abstentions | 6 | 6 | 0 |
| Validator rejections | 3 | 1 | -2 |
| Execution errors or interruptions | 0 | 1 | +1 |
| Schema characters | 17757 | 17450 | -307 |
| Input tokens | 6381 | 6502 | +121 |
| Output tokens | 1169 | 1098 | -71 |
| Estimated token cost | `$0.013395` | `$0.013090` | `-$0.000305` |
| Full-table-recall tasks | 15 | 14 | -1 |
| Full-column-recall tasks | 14 | 10 | -4 |
| Retrieval-miss tasks | 6 | 10 | +4 |

B4 improved task `1351`, regressed tasks `24` and `740`, and left correctness status unchanged on 17 tasks. It used 1.7% fewer schema characters and 2.3% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
