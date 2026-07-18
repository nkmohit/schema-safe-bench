# B0 versus B4 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B0 supplies the full schema; B4 applies the locked 12-hit hybrid fusion policy.

| Metric | B0 full schema | B4 hybrid | Delta |
|---|---:|---:|---:|
| Correct | 6 | 3 | -3 |
| Accuracy | 30% | 15% | -15 percentage points |
| Safe abstentions | 2 | 6 | +4 |
| Validator rejections | 0 | 1 | +1 |
| Execution errors or interruptions | 2 | 1 | -1 |
| Schema characters | 38634 | 17450 | -21184 |
| Input tokens | 11588 | 6502 | -5086 |
| Output tokens | 1311 | 1098 | -213 |
| Estimated token cost | `$0.019454` | `$0.013090` | `-$0.006364` |
| Full-table-recall tasks | 20 | 14 | -6 |
| Full-column-recall tasks | 20 | 10 | -10 |
| Retrieval-miss tasks | 0 | 10 | +10 |

B4 recorded no correctness improvements, regressed tasks `24`, `47`, and `740`, and left correctness status unchanged on 17 tasks. It used 54.8% fewer schema characters and 32.7% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
