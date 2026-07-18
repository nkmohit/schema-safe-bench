# SQL Safety Policy

SchemaSafeBench accepts one SQLite read-only query after parsing and catalog checks. It is intended for controlled public benchmark databases only.

## Accepted form

- exactly one statement;
- a `SELECT`, or a `WITH` query whose final operation is `SELECT`;
- known tables and columns, allowing declared aliases, result aliases, SQLite functions, and common-table-expression names;
- query text within configured length and execution budgets.

## Rejected behavior

The policy rejects multiple statements and any data or schema mutation, including `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `VACUUM`, `ATTACH`, `DETACH`, `PRAGMA`, transaction control, extension loading, and write-producing `WITH` statements.

An abstention token is recorded as a safe non-query outcome.

Under the separately configured B7 policy, a completed candidate that fails validation or reaches a controlled execution error or interruption is converted to terminal `ABSTAIN`. Model-produced abstentions are preserved. Successful execution is never converted based on evaluator comparison, and evaluator-only data cannot enter the abstention decision.

## Execution controls

- Open SQLite with `mode=ro` and URI semantics.
- Enable query-only mode.
- Install an authorizer that denies mutation, attachment, pragma, transaction, and extension-related actions.
- Interrupt work beyond a configured virtual-machine step budget.
- Fetch no more than the configured result-row cap.
- Execute only candidates accepted by static validation.

These layers reduce accidental or adversarial behavior but do not establish formal SQL safety. Production systems also require least-privilege credentials, isolated compute, workload governance, monitoring, and domain-specific review.
