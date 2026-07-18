# B4 versus B6 GPT-5.6 Luna Smoke Comparison

This paired comparison holds every B4 first-pass artifact fixed. B6 adds one repair request only for first-pass validator rejection or controlled execution error or interruption.

| Metric | B4 hybrid | B6 bounded repair | Delta |
|---|---:|---:|---:|
| Correct | 3 | 3 | 0 |
| Accuracy | 15% | 15% | 0 percentage points |
| Safe abstentions | 6 | 7 | +1 |
| Validator rejections | 1 | 1 | 0 |
| Execution errors or interruptions | 1 | 0 | -1 |
| Schema characters | 17450 | 17450 | 0 |
| Input tokens | 6502 | 7178 | +676 |
| Output tokens | 1098 | 1265 | +167 |
| Estimated token cost | `$0.013090` | `$0.014768` | `+$0.001678` |

B6 had no improved or regressed correctness cases. Task `116` changed from execution failure to validator rejection, and task `1185` changed from validator rejection to safe abstention. The other 18 task outcomes were unchanged. Because the schema packs are identical, schema-evidence aggregates are identical.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes, total B6 accounting, and both evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim.
