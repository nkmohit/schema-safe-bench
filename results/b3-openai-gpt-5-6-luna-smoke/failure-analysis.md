# B3 Representative Cases

These cases come directly from the committed trace. They illustrate observed behavior and do not assign causality from correlation alone.

## Correct with complete evidence: task 1042

The question asks for leagues whose average home-team goals exceeded away-team goals in the 2009/2010 season. Dense retrieval exposed every required table and column, and the generated grouped query was execution-equivalent to the reference. This task improved over B2's abstention and remained correct relative to B0 and B1.

## Correct despite incomplete reference evidence: task 414

The generated query over `set_translations` and `cards` was execution-equivalent even though the pack omitted the reference query's `sets` table and three of its columns. It improved over B0 and B1 and remained correct relative to B2. This case demonstrates why reference-identifier recall measures prompt evidence rather than being a necessary definition of semantic equivalence.

## Retrieval miss with abstention: task 24

The pack included `frpm` evidence but omitted `satscores`, `satscores.cds`, and `satscores.NumGE1500`. The model returned `ABSTAIN`. B0 and B1 had complete schema evidence and correct outputs for this task, while B2 also missed the required `satscores` evidence and abstained.

## Retrieval miss with semantic mismatch: task 800

The pack included `superhero` but omitted `colour` and its required identifiers. The generated query used an unrelated `hero_attribute` subquery to infer blue eyes, executed successfully, and returned a non-equivalent result. B0 and B1 were correct on this task; B2 safely abstained.

## Complete evidence but semantic mismatch: task 1028

All reference tables and columns were prompt-visible, and the candidate executed successfully. It filtered `Match.season` with `2010`, which did not match the benchmark's required season semantics. Dense retrieval cannot by itself resolve value interpretation or guarantee correct aggregation logic.

## Complete evidence with validator rejection: task 218

The pack contained every reference table and column, but the response treated `molecule.label` as a carcinogenic classification and used an invalid multi-CTE form under the locked validator contract. The validator rejected it before execution. Complete schema evidence does not imply policy-valid or semantically correct SQL.

## Value-grounding mismatch: task 459

The question names two card values. The pack exposed `cards.convertedManaCost` but omitted the reference column `cards.name`; the response filtered `flavorName` instead and produced a semantic mismatch. Schema-only dense retrieval does not retrieve database values or establish which column contains a named entity.

## Interpretation limits

- The manifest contains 20 tasks and cannot support broad benchmark or significance claims.
- Hosted outputs are not claimed deterministic; comparisons retain each run's recorded response.
- Reference SQL is consulted only after generation to label identifier coverage and execution equivalence.
- A retrieval miss does not by itself explain an abstention, rejection, or semantic mismatch.
- A full-recall pack may still contain distractors or omit values and task semantics needed for a correct query.
- The pinned embedding snapshot narrows local variance but does not make hosted generation deterministic.
