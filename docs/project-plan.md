# Project Plan

This plan orders work by dependency and research validity.

## Project boundary

SchemaSafeBench is a public evaluation harness over existing public text-to-SQL tasks. It does not create a new benchmark dataset, expose proprietary materials, fine-tune a model, or claim production database security.

## Stage A: Reproducible foundation

- [x] Python 3.12 package managed by `uv` with a committed lockfile.
- [x] Public-data and credential boundaries in documentation and ignore rules.
- [x] CI for formatting, linting, and offline tests.
- [x] Contribution, conduct, security, citation, and issue templates.
- [x] Versioned dataset, method, and run configuration directories.

Acceptance: a fresh checkout installs from the lockfile, the CLI starts, and CI needs neither benchmark downloads nor model credentials.

## Stage B: Dataset and catalog

- [x] Normalize common BIRD Mini-Dev JSON fields into typed tasks.
- [x] Filter the primary task set to one-statement read queries.
- [x] Create a deterministic task manifest independent of input ordering.
- [x] Discover database files without path traversal.
- [x] Extract SQLite tables, columns, primary keys, and foreign keys read-only.
- [x] Record the chosen upstream dataset revision and archive digest.
- [x] Generate the 20-task manifest from the acquired official assets.

Acceptance: one command validates the task file and another produces a stable machine-readable catalog for any configured database.

## Stage C: Safety and evaluation

- [x] Parse exactly one `SELECT` or read-only `WITH` query.
- [x] Reject mutation, unknown schema objects, blocked functions, and abstentions appropriately.
- [x] Require a successful validation result before execution.
- [x] Open SQLite read-only with query-only mode, an authorizer, a work budget, and a row cap.
- [x] Compare successful results with explicit ordered or bag semantics.
- [x] Preserve structured rejection and execution categories.
- [ ] Cross-check result equivalence against the official BIRD evaluator on a public sample.

Acceptance: tests demonstrate that rejected SQL cannot reach the executor and equivalent results are recognized under the declared policy.

## Stage D: Schema context and generation contracts

- [x] Build table and column retrieval documents.
- [x] Implement deterministic BM25 retrieval.
- [x] Define dense retrieval through an injected embedding function.
- [x] Fuse lexical and dense ranks for the hybrid baseline.
- [x] Serialize schema packs with relevant join edges.
- [x] Version generation and one-repair prompt contracts.
- [x] Define a provider-neutral generator interface and offline replay adapter.
- [ ] Add one hosted-model adapter after credentials and provider choice are configured locally.
- [ ] Record the embedding model identifier and immutable revision for dense runs.

Acceptance: prompts contain only the question and allowed schema context; gold SQL has no API path into generation or repair builders.

## Stage E: Auditable experiments

- [x] Evaluate saved predictions through the same validator, executor, and comparator used by provider runs.
- [x] Write non-overwriting JSONL traces and a structured run summary.
- [x] Record raw output separately from extracted candidate SQL.
- [x] Bound repair count in the trace schema.
- [ ] Run B0 through B7 on the deterministic public smoke manifest.
- [ ] Freeze the full evaluation configuration before producing final BIRD results.
- [ ] Publish raw distributable traces, aggregate tables, and representative failure cases.
- [ ] Add paired uncertainty and significance analysis only when complete paired predictions exist.

Acceptance: every reported number resolves to a task manifest, configuration, code revision, trace set, and aggregation policy.

## Stage F: Optional extensions

- [ ] Add a static result browser if it improves failure inspection.
- [ ] Replicate the frozen protocol with additional model families.
- [ ] Add Spider 2.0-Lite as a separately labelled stress evaluation.
- [ ] Add container packaging only after the native reproducibility path remains verified.

These extensions cannot change or obscure the primary BIRD protocol and must not block publication of honest negative findings.
