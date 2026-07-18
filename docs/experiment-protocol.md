# Experiment Protocol

## Research question

On public text-to-SQL tasks, can schema-aware retrieval plus validation and one bounded repair improve execution correctness and identifier grounding over direct full-schema prompting while preserving predictable safety and cost?

## Primary task set

Use the 500 high-quality SELECT-only tasks from BIRD Mini-Dev. Exclude CRUD-oriented tasks. A deterministic 20-task manifest is used for pipeline smoke testing, and every smaller run must be labelled as a sample rather than a complete benchmark result.

## Controlled variables

For a method comparison, keep these fixed:

- task IDs and database files;
- generator provider, exact model identifier, and sampling settings;
- prompt contract except for the schema-context strategy under test;
- query policy, execution limits, and evaluator;
- random seeds and result normalization rules.

The generator never receives reference SQL, reference results, or labels derived from them.

## Methods

The canonical method IDs are B0 through B7 as defined in the README. Dense and reranking components are optional dependencies and must record their exact model identifiers and revisions.

### B1 length-truncation policy

B1 applies `catalog-character-prefix-v1`, a fixed 1,000-Unicode-code-point ceiling to the canonical catalog serialization. Tables follow the catalog's case-insensitive name order, columns follow SQLite declaration order, and foreign keys are sorted. The pack admits only complete column declarations; a foreign key appears only when both endpoint columns are visible. Construction stops before the first declaration that would exceed the ceiling, so the structured tables, foreign keys, and serialized prompt context describe the same visible schema.

The policy, manifest digest, ordering rules, and smoke-manifest distribution are locked in [`data/provenance/b1-schema-truncation.json`](../data/provenance/b1-schema-truncation.json). The 1,000-character ceiling truncates 15 of the 20 smoke tasks across eight databases while leaving five tasks whose complete schemas fit the limit unchanged. B1 is therefore a controlled context-pressure baseline, not relevance-based retrieval.

### B2 BM25 retrieval policy

B2 applies `bm25-schema-documents-v1`. ASCII-alphanumeric tokens are extracted after Unicode casefolding. Each catalog contributes one table document followed by one document per column. `rank_bm25.BM25Okapi` uses `k1=1.5`, `b=0.75`, and `epsilon=0.25`; the first 12 documents are selected by descending score and ascending document ID. Zero-score documents remain eligible when needed to fill the fixed selection count.

A table-document hit exposes the full selected table. Column-only hits expose the selected columns, primary keys, and endpoints of foreign keys between selected tables. Foreign-key lines are lexicographically ordered, and every endpoint they name is present in the structured prompt context. The exact document templates, ranking rules, dependency version, selection rule, manifest digest, and serialization contract are locked in [`data/provenance/b2-bm25-schema-retrieval.json`](../data/provenance/b2-bm25-schema-retrieval.json).

Reference SQL does not participate in document construction, retrieval, schema-pack assembly, request creation, or generation. After a response has been recorded, evaluator-only `reference-sql-identifiers-v1` analysis validates the public reference SQL and measures whether its referenced tables and columns were prompt-visible. Empty required-identifier sets receive recall 1.0; empty selected-identifier sets receive precision 1.0 only when the corresponding required set is also empty.

## Required records

Each task trace records:

- run ID, task ID, database ID, and method ID;
- configuration digest and software revision;
- selected schema objects, ranks, scores, and serialized schema pack;
- prompt-template version and model settings;
- raw generator response and extracted candidate SQL;
- validation findings and optional repair record;
- execution status, result shape, and controlled error category;
- equivalence outcome and failure label;
- evaluator-only required, selected, and missing schema identifiers;
- token usage, request latency, and estimated cost when provided.

## Metrics

The primary metric is execution accuracy: candidate and reference queries produce equivalent results on the same database under `bird-execution-v1`. This policy matches the checksum-pinned official BIRD evaluator by comparing returned SQLite row tuples as sets, ignoring order and duplicate multiplicity. `strict-v1` is available only for diagnostics and must not be reported as official-compatible BIRD execution accuracy. See [evaluator-compatibility.md](evaluator-compatibility.md).

Any candidate or reference result truncated by the configured row cap is non-comparable. It must remain visible in traces and cannot be counted as correct from partial rows.

Reliability metrics include identifier-validity rate, schema-evidence recall and precision, policy-violation rate, repair gain, abstention precision and coverage, execution-error rate, prompt tokens, request latency distribution, and estimated cost.

## Result integrity

- Preserve raw model output before extraction or repair.
- Append traces; do not silently overwrite prior runs.
- Record exclusions and failed requests rather than dropping them.
- Separate implementation debugging from outcome-driven prompt tuning.
- Publish negative and mixed findings.
- Do not compare with external scores unless dataset version, task subset, execution engine, and evaluator protocol match.
