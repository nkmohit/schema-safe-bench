# B6 Repair Cases

These cases come directly from the committed B6 trace. The eligibility decision uses first-pass validation and controlled execution only; reference SQL and semantic comparison are evaluator-only.

## Controlled interruption to validator rejection: task 116

The B4 candidate passed validation but reached `query_budget_exceeded`. Its single repair request received the unchanged B4 schema pack, candidate, and normalized error `execution:query_budget_exceeded`. The repaired query replaced the scalar balance CTE with a joined aggregation, but validation rejected qualifier `f` in the generated CTE join. The terminal state changed, but the task remained incorrect.

The schema pack omitted the reference `account` table and `account.account_id`. That evaluator-only fact was not available to eligibility or repair. The case cannot establish whether broader evidence, validator CTE handling, or another query structure would change the result.

## Validator rejection to safe abstention: task 1185

The B4 candidate fabricated `total cholesterol` columns and was rejected. The repair request contained the unchanged schema pack, rejected candidate, and normalized `unknown_column` identifiers. Luna returned `ABSTAIN`, which the validator accepted as the benchmark's explicit safe-abstention state. The terminal state became safer but did not become correct.

Evaluator-only evidence shows that the B4 pack omitted the reference `Laboratory` table and required date, patient, and cholesterol columns. Those identifiers were never supplied to the repair request.

## Unrepaired cases

All six B4 abstentions remained untouched. All successful executions also remained untouched, including nine semantic mismatches and three correct queries. This is required by the frozen policy: semantic comparison cannot trigger repair, and `ABSTAIN` cannot be retried.

## Interpretation limits

- Two eligible cases cannot support a broad repair-effect claim.
- Repair reduced controlled execution failures and increased safe abstention, but correctness remained unchanged.
- A validator rejection after repair is a failed repair outcome, even when it avoids executing an expensive query.
- The validator's treatment of the generated CTE alias is part of the observed pipeline behavior and is not silently corrected in this result.
- Hosted outputs are replayed from request-digest-checked recordings; they are not claimed to be inherently deterministic.
