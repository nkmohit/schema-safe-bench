# B7 Abstention Cases

These cases come directly from the committed B7 trace. Abstention enforcement uses only provider completion, first-pass validation, and controlled execution. Reference SQL, semantic comparison, task evidence, and schema-evidence labels are evaluator-only.

## Controlled interruption to enforced abstention: task 116

The unchanged B4 candidate passed validation but reached `query_budget_exceeded`. B7 converted the terminal candidate to `ABSTAIN` without a model call. The original raw output, candidate, generation metadata, request digest, and normalized execution cause remain in the trace. This avoids an execution-failure terminal state but does not produce a correct answer.

Evaluator-only evidence shows that the schema pack omitted the reference `account` table and `account.account_id`. That information did not enter the decision.

## Validator rejection to enforced abstention: task 1185

The unchanged B4 candidate fabricated `total cholesterol` columns. Static validation rejected it, and B7 converted the terminal candidate to `ABSTAIN`. The original rejection and identifiers remain auditable. The policy avoids returning invalid SQL but cannot recover the requested answer.

Evaluator-only evidence shows that the schema pack omitted the reference `Laboratory` table and required columns. Those identifiers were unavailable to enforcement.

## Preserved model abstentions

Tasks `24`, `1155`, `740`, `898`, `1464`, and `637` already contained exact model output `ABSTAIN`; B7 preserved them. Their overall abstention precision cannot be calculated because the recording contains no counterfactual SQL from the same request.

## Preserved successful executions

All 12 successfully executing B4 candidates remained queries: three correct and nine semantic mismatches. The mismatches were not abstained from because semantic equivalence is evaluator-only and unavailable to the B7 decision. This is an important limitation: validator/executor-gated abstention removes structurally unsafe terminal states but cannot detect wrong, executable SQL.

## Interpretation limits

- The policy changes terminal safety classification, not answer correctness.
- Unsafe-terminal avoidance is guaranteed for eligible cases and must not be presented as learned confidence quality.
- Model abstention precision is not identifiable without a predeclared counterfactual-generation protocol.
- The smoke manifest cannot support broad or significance claims.
- Hosted responses remain nondeterministic in general; the committed B4 recording is the exact replay source.
