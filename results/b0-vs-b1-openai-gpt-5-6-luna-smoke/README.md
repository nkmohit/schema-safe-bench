# B0 versus B1 GPT-5.6 Luna Smoke Comparison

This directory contains a paired comparison generated from the committed B0 and B1 traces with identical task IDs. Both runs use `gpt-5.6-luna`, prompt version `sqlite-readonly-v1`, temperature `0.0`, reasoning effort `none`, the same 20-task manifest, and the same safety and official-compatible evaluation path. The schema-context strategy is the intended method difference.

| Metric | B0 full schema | B1 truncated schema | Delta |
|---|---:|---:|---:|
| Correct | 6 | 4 | -2 |
| Accuracy | 30% | 20% | -10 percentage points |
| Safe abstentions | 2 | 6 | +4 |
| Validator rejections | 0 | 3 | +3 |
| Execution errors or interruptions | 2 | 0 | -2 |
| Schema characters | 38634 | 17757 | -20877 |
| Input tokens | 11588 | 6381 | -5207 |
| Output tokens | 1311 | 1169 | -142 |
| Estimated token cost | `$0.019454` | `$0.013395` | `-$0.006059` |

B1 reduced aggregate schema characters by about 54%, input tokens by about 45%, and estimated token cost by about 31%. It produced no correctness improvements, regressed tasks `47` and `1351`, and left correctness status unchanged on the other 18 tasks. The absence of execution failures in B1 reflects abstentions and validator rejections rather than higher execution accuracy.

The machine-readable [`comparison.json`](comparison.json) includes each paired task's outcome category and schema-character counts, both configuration digests, both implementation revisions, failure-category aggregates, and all metric deltas. Reproduce it with:

```bash
uv run schema-safe-bench results compare \
  --baseline results/b0-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --treatment results/b1-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --output results/local/b0-vs-b1-comparison.json
```

This is a smoke comparison, not a complete benchmark result, causal estimate, or significance claim. Five prompts were identical across methods because the full schema already fit the B1 ceiling; one of those fresh hosted responses differed, so provider nondeterminism remains visible rather than being hidden.
