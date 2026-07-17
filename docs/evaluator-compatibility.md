# Official BIRD Evaluator Compatibility

SchemaSafeBench uses the official BIRD Mini-Dev execution-accuracy semantics for its primary correctness metric. This document records the pinned upstream source, the observed behavior, the compatibility fixes, and the reproducible cross-check.

## Pinned upstream source

| Item | Pinned value |
|---|---|
| Repository | `https://github.com/bird-bench/mini_dev` |
| Repository revision | `b3d4bcbbae9a96934ad812551eb400c7a3b23c12` |
| Evaluator source revision | `f9d2750c9b53639820c9d47f6d7a5e5025c780ab` |
| `evaluation/evaluation_ex.py` SHA-256 | `da1bbcd4530be83692d7c650c814ea9704bb710d0c953eb75d02ccb38233cf89` |
| `evaluation/evaluation_utils.py` SHA-256 | `f6943d249caac5aeaef9bce21d43dbf29dcef85a0c965a76df032a9542f308bf` |

The machine-readable record is [`data/provenance/bird-evaluator.json`](../data/provenance/bird-evaluator.json). Upstream source is not vendored. The compatibility command verifies the Git revision and both file digests before loading only the official `calculate_ex` function into an isolated namespace.

## Official EX semantics

The pinned evaluator executes candidate and reference SQL on the same database and compares the returned row tuples as Python sets. Consequently:

- row order is ignored, including queries containing `ORDER BY` or `LIMIT`;
- duplicate multiplicity is ignored;
- `NULL` values compare through Python `None` equality;
- SQLite integers and numerically equal floats compare equal;
- distinct floating-point values are not rounded before comparison;
- two empty result sets compare equal regardless of cursor column metadata;
- an execution exception or evaluator timeout is incorrect.

SchemaSafeBench exposes this as `bird-execution-v1`. A separate `strict-v1` diagnostic policy preserves row order when requested, duplicate multiplicity, and column-count checks. Published BIRD execution accuracy must use `bird-execution-v1`.

## Confirmed fixes

Before this cross-check, SchemaSafeBench used bag semantics, inferred order sensitivity from reference SQL, rounded floats during normalization, and compared empty-result column counts. Those behaviors did not match the official EX evaluator. The primary policy now uses native set equality over SQLite row tuples.

The configured evaluation row cap was also raised to `100000`. One committed smoke task returns `1165` rows and was truncated by the earlier cap. Results that exceed the declared cap remain non-comparable: the project does not silently claim equivalence from partial rows.

## Reproduce the cross-check

Prepare the official source outside this repository:

```bash
git clone https://github.com/bird-bench/mini_dev.git /tmp/bird-mini-dev-evaluator
git -C /tmp/bird-mini-dev-evaluator checkout b3d4bcbbae9a96934ad812551eb400c7a3b23c12
```

Run the compatibility gate:

```bash
uv run schema-safe-bench evaluation compatibility \
  --official-checkout /tmp/bird-mini-dev-evaluator \
  --tasks data/raw/bird-minidev/mini_dev_sqlite.json \
  --databases data/raw/bird-minidev/dev_databases \
  --manifest data/processed/manifests/bird-minidev-select-smoke.json \
  --output data/processed/manifests/bird-evaluator-compatibility.json
```

The command exits non-zero for an upstream revision mismatch, checksum mismatch, semantic edge-case mismatch, execution-path mismatch, or smoke-task comparison mismatch.

## Verified result

The committed report records:

| Check | Matching |
|---|---:|
| Semantic edge cases | 7 / 7 |
| Smoke-manifest tasks | 20 / 20 |
| Recorded mismatches | 0 |

The edge cases cover ordering, duplicates, `NULL`, integer/float equality, floating-point precision, empty-result metadata, and execution failure. The smoke check executes each selected reference query through both the official-style SQLite path and the SchemaSafeBench read-only validated path. This proves evaluator compatibility for the declared cases; it is not a model-performance result.
