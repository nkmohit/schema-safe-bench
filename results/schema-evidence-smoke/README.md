# Evaluator-only Schema Evidence

These reports apply `reference-sql-identifiers-v1` to the committed B0 through B4 traces. Each report records the SHA-256 digest of its source trace and compares identifiers validated from public reference SQL with the schema context already visible in the corresponding prompt.

| Metric | B0 | B1 | B2 | B3 | B4 |
|---|---:|---:|---:|---:|---:|
| Full-table-recall tasks | 20 | 15 | 10 | 13 | 14 |
| Full-column-recall tasks | 20 | 14 | 8 | 9 | 10 |
| Tasks with any retrieval miss | 0 | 6 | 12 | 11 | 10 |
| Macro table recall | 1.0000 | 0.8500 | 0.7500 | 0.8083 | 0.8500 |
| Macro column recall | 1.0000 | 0.8396 | 0.7256 | 0.7413 | 0.7731 |
| Macro table precision | 0.3818 | 0.4682 | 0.5092 | 0.5667 | 0.5479 |
| Macro column precision | 0.1263 | 0.1488 | 0.1869 | 0.1627 | 0.1806 |

The analysis is evaluator-only and occurs after generation. Required identifiers never enter retrieval or generation. Precision and recall describe prompt-visible identifiers, not SQL correctness or causal effects.
