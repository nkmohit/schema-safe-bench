# B0 versus B5 GPT-5.6 Luna Smoke Comparison

This paired comparison holds the task IDs, model, prompt contract, generation settings, safety controls, and official-compatible evaluation fixed. B0 supplies the full catalog; B5 selects 12 documents after reranking a fixed B4 candidate set.

| Metric | B0 full schema | B5 reranked | Delta |
|---|---:|---:|---:|
| Correct | 6 | 2 | -4 |
| Accuracy | 30% | 10% | -20 percentage points |
| Safe abstentions | 2 | 8 | +6 |
| Validator rejections | 0 | 2 | +2 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 12985 | -25649 |
| Input tokens | 11588 | 5366 | -6222 |
| Output tokens | 1311 | 784 | -527 |
| Estimated token cost | `$0.019454` | `$0.010070` | `-$0.009384` |
| Full-table-recall tasks | 20 | 11 | -9 |
| Full-column-recall tasks | 20 | 8 | -12 |
| Retrieval-miss tasks | 0 | 12 | +12 |

B5 had no improved tasks, regressed tasks `24`, `47`, `740`, and `800`, and left correctness status unchanged on 16 tasks. It used 66.4% fewer schema characters and 48.2% lower estimated token cost.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evaluator-only evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The methods use separately recorded hosted responses, so provider nondeterminism cannot be excluded.
