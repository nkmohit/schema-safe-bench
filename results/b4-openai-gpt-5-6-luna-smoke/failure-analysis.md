# B4 Representative Cases

These cases come directly from the committed trace. They illustrate observed behavior and do not assign causality from correlation alone.

## Correct with complete evidence: task 800

The question asks for the percentage of superheroes with blue eyes. The fused pack exposed `superhero.eye_colour_id`, `colour.colour`, both tables, and their join endpoints. The generated aggregation was execution-equivalent to the reference. This task improved relative to B2 and B3, but one separately recorded hosted transition cannot establish that fusion caused the improvement.

## Correct with complementary component ranks: task 1042

The question asks for leagues where average home-team goals exceed away-team goals. The leading fused hits combined strong lexical and dense placements for both goal columns, and the pack contained every required identifier. The generated grouped query was correct. This improved over B2 and remained correct relative to B3.

## Correct major lookup: task 1351

The pack contained the `major` and `member` identifiers required for Brent Thomason's major. BM25 and dense retrieval ranked the relevant documents differently, while fusion retained the necessary table, join key, name fields, and output column. The candidate was correct and improved relative to B1.

## Retrieval miss with abstention: task 24

The fused selection concentrated on meal-related `frpm` evidence and omitted `satscores`, `satscores.cds`, and `satscores.NumGE1500`. The model returned `ABSTAIN`. B0 and B1 had complete evidence and correct outputs for this task; B2 and B3 also missed required evidence and abstained.

## Paired regression with incomplete evidence: task 414

The pack included `set_translations`, `sets`, and most required columns but omitted `sets.baseSetSize`. The response filtered text in `set_translations.translation` instead of applying the card-count condition and produced a semantic mismatch. B2 and B3 were correct on their separately recorded responses. The transition does not prove that the omitted column alone caused the regression.

## Complete evidence but semantic mismatch: task 1028

All reference tables and columns were prompt-visible, and the candidate executed successfully. It filtered the season as `2010`, which did not match the benchmark's required interpretation. Full identifier recall cannot supply missing value semantics or guarantee correct SQL logic.

## Retrieval miss with bounded execution interruption: task 116

The pack omitted the reference `account` table and `account.account_id`. The generated query used `loan` and `trans`, passed validation, and reached the fixed SQLite work limit. The interruption is retained as `query_budget_exceeded`; it is not counted as correct or silently retried.

## Retrieval miss with validator rejection: task 1185

The pack omitted `Laboratory` and its required date, patient ID, and cholesterol columns. The response fabricated aliases and a `total cholesterol` identifier. The validator rejected the unknown column before execution.

## Interpretation limits

- The manifest contains 20 tasks and cannot support broad benchmark or significance claims.
- Hosted outputs are not claimed deterministic; comparisons retain each run's recorded response.
- Reference SQL is consulted only after generation to label identifier coverage and execution equivalence.
- A retrieval miss does not by itself explain an abstention, rejection, interruption, or semantic mismatch.
- A full-recall pack may still contain distractors or omit values and task semantics needed for a correct query.
- Fusion combines rankings; it does not calibrate raw component scores or retrieve database values.
