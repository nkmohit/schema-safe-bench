# B0 versus B6 GPT-5.6 Luna Smoke Comparison

This paired comparison contrasts full-schema B0 with B6, which reuses the B4 hybrid first pass and adds bounded validator/executor-triggered repair.

| Metric | B0 full schema | B6 bounded repair | Delta |
|---|---:|---:|---:|
| Correct | 6 | 3 | -3 |
| Accuracy | 30% | 15% | -15 percentage points |
| Safe abstentions | 2 | 7 | +5 |
| Validator rejections | 0 | 1 | +1 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 17450 | -21184 |
| Input tokens | 11588 | 7178 | -4410 |
| Output tokens | 1311 | 1265 | -46 |
| Estimated token cost | `$0.019454` | `$0.014768` | `-$0.004686` |

B6 had no improved tasks relative to B0 and regressed tasks `24`, `47`, and `740`. These methods use separately recorded first-pass responses, so this comparison does not isolate the causal effect of retrieval or repair. The machine-readable [`comparison.json`](comparison.json) preserves all paired outcomes and evidence aggregates.

This is a descriptive smoke comparison, not a complete benchmark result or significance claim.
