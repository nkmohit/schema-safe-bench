# B4 versus B7 GPT-5.6 Luna Smoke Comparison

This paired comparison holds every B4 schema pack, request, hosted response, digest, and candidate fixed. B7 adds deterministic terminal abstention only for validator rejection or controlled execution error or interruption.

| Metric | B4 hybrid | B7 abstention | Delta |
|---|---:|---:|---:|
| Correct | 3 | 3 | 0 |
| Accuracy | 15% | 15% | 0 percentage points |
| Safe abstentions | 6 | 8 | +2 |
| Validator rejections | 1 | 0 | -1 |
| Execution errors or interruptions | 1 | 0 | -1 |
| Schema characters | 17450 | 17450 | 0 |
| Input tokens | 6502 | 6502 | 0 |
| Output tokens | 1098 | 1098 | 0 |
| Estimated token cost | `$0.013090` | `$0.013090` | `$0.000000` |

B7 has no improved or regressed correctness cases. Task `116` changes from execution failure to safe abstention, and task `1185` changes from validator rejection to safe abstention. The other 18 paired outcomes remain unchanged. Schema evidence is identical.

The machine-readable [`comparison.json`](comparison.json) preserves paired outcomes and both evidence aggregates. This is a descriptive smoke comparison, not a causal estimate, complete benchmark result, or significance claim. The policy prevents eligible unsafe terminal states; it does not detect semantic mismatches.
