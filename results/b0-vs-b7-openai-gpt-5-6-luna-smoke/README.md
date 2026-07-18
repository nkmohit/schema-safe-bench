# B0 versus B7 GPT-5.6 Luna Smoke Comparison

This paired context comparison contrasts full-schema B0 with B7, which reuses the B4 hybrid first pass and applies deterministic terminal abstention.

| Metric | B0 full schema | B7 abstention | Delta |
|---|---:|---:|---:|
| Correct | 6 | 3 | -3 |
| Accuracy | 30% | 15% | -15 percentage points |
| Safe abstentions | 2 | 8 | +6 |
| Validator rejections | 0 | 0 | 0 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 17450 | -21184 |
| Input tokens | 11588 | 6502 | -5086 |
| Output tokens | 1311 | 1098 | -213 |
| Estimated token cost | `$0.019454` | `$0.013090` | `-$0.006364` |

B7 has no improved tasks and regresses tasks `24`, `47`, and `740` relative to B0. These methods use different first-pass schema contexts and separately recorded hosted responses, so the comparison does not isolate the causal effect of abstention. The machine-readable [`comparison.json`](comparison.json) preserves all paired outcomes and evidence aggregates.

This is a descriptive smoke comparison, not a complete benchmark result or significance claim.
