# Full-Evaluation Protocol Freeze

The complete B0-B7 protocol is frozen over one population derived from the pinned BIRD
Mini-Dev SQLite task source. This milestone authorizes no expanded hosted request.

## Population and assets

- Raw task records: 500.
- Included SELECT-only tasks: 500.
- Excluded tasks: 0.
- Databases: 11.
- Difficulty labels: 148 simple, 250 moderate, and 102 challenging.
- Ordering: normalized numeric task ID ascending, with a deterministic text-ID fallback.
- Inclusion inputs: task ID, database ID, question presence, and reference SQL structure only.
- Prohibited inclusion inputs: model outputs, execution results, evaluator labels, and equivalence
  outcomes.

The machine-readable population is
[`bird-minidev-select-full.json`](../data/processed/manifests/bird-minidev-select-full.json).
The corresponding
[`exclusion report`](../data/processed/manifests/bird-minidev-select-full-exclusions.json)
records every reason category, including zero-count categories. The
[`database inventory`](../data/provenance/bird-minidev-full-databases.json) records the relative
path, byte size, database SHA-256, canonical catalog SHA-256, and WAL state for every database.

## Frozen paired controls

The separately named configs under [`configs/runs/full`](../configs/runs/full) lock B0-B7 to the
same task source, manifest, database root, `gpt-5.6-luna` Responses configuration, prompt
contract, `$5` run cap, `$95` cumulative cap, execution sandbox, and evaluator policy. B6 and B7
reference the full B4 config, recording, and trace paths. All full outputs and recordings are
separate from smoke artifacts and fail on overwrite.

Reference SQL and results, task evidence, evaluator labels, equivalence outcomes, and
evaluator-derived identifiers remain outside retrieval, schema packing, request construction,
validation, repair, and abstention decisions.

## Provider-free cost preflight

The preflight found 20 reusable first-pass recordings for each of B0-B5 and two reusable B6
repair recordings. B7 creates no hosted request. The conservative plan contains 3,378 missing
requests at an upper-bound reservation of `$61.42467700`; the existing ledger balance is
`$0.08052200`, so the cumulative `$95` cap remains satisfied and total project exposure remains
below `$100`.

The protocol is `blocked_by_budget_and_verification`. The atomic full runs do not fit the
unchanged `$5` per-run cap:

| Method | Reusable | Missing upper bound | Reservation | Fits `$5` |
|---|---:|---:|---:|:---:|
| B0 | 20 | 480 | `$5.95169400` | No |
| B1 | 20 | 480 | `$5.49636500` | No |
| B2 | 20 | 480 | `$5.95169400` | No |
| B3 | 20 | 480 | `$5.95169400` | No |
| B4 | 20 | 480 | `$5.95169400` | No |
| B5 | 20 | 480 | `$5.95169400` | No |
| B6 | 2 | 498 | `$26.16984200` | No |
| B7 | 20 | 0 | `$0.00000000` | Yes |

B0 uses its exact full-catalog request ceiling. B1 uses its exact 1,000-character context
ceiling. B2-B5 conservatively reserve as if every missing request received the full catalog,
which bounds their retrieval-selected schema prompts. B6 conservatively reserves one repair for
every unrecorded task with a full schema and bounded maximum candidate and error text, without
assuming which future first-pass responses will be eligible.

No cap was raised and no task was removed. Expanded execution remains blocked unless a new,
explicitly reviewed execution strategy can preserve the frozen population and controls while
satisfying the existing caps.

The full asset gate also executed every reference query through the frozen validator and
executor. Validation accepted all 500 references. Under the frozen 1,000,000-step query budget,
428 references completed and 72 were safely interrupted. Those tasks remain in the paired
manifest; they are recorded in
[`bird-minidev-select-full-verification.json`](../data/processed/manifests/bird-minidev-select-full-verification.json)
and cannot be silently discarded or counted as correct. This verification constraint must also
be resolved before expanded execution is authorized.

## Regeneration

With the pinned public raw assets present, regenerate and verify the complete freeze without an
API key:

```bash
env -u OPENAI_API_KEY uv run schema-safe-bench evaluation freeze \
  --config configs/evaluation/bird-minidev-b0-b7-full-freeze.yaml
```

Exit code `2` is the expected fail-closed result while the per-run budget constraint remains.
The complete machine-readable readiness result is
[`results/full-evaluation-readiness.json`](../results/full-evaluation-readiness.json).
