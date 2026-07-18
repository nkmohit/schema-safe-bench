# B5 Representative Cases

These cases come directly from the committed trace. They illustrate observed behavior and do not assign causality from correlation alone.

## Correct with complete multi-table evidence: task 1042

The question asks for leagues where average home-team goals exceed away-team goals in the 2009/2010 season. The reranked pack exposed `League.name`, `League.id`, `Match.league_id`, both goal columns, and the selected-table join edge. The generated grouped query was execution-equivalent to the reference. This task improved relative to B2 and remained correct relative to B0, B3, and B4.

## Correct compact lookup: task 1351

The pack contained the `member` name fields, `member.link_to_major`, `major.major_id`, and `major.major_name` required for Brent Thomason's major. The generated join was correct. The task improved relative to B1 and remained correct relative to B0, B2, B3, and B4.

## Retrieval miss with abstention: task 24

The selection concentrated on free-meal fields in `frpm` and omitted `satscores`, `satscores.cds`, and `satscores.NumGE1500`. The model returned `ABSTAIN`. B0 and B1 had separately recorded correct outputs with broader evidence; the transition does not prove that the omitted table alone caused the abstention.

## B4 regression with validator rejection: task 800

The pack retained `superhero.eye_colour_id` but omitted the `colour` table and its `id` and `colour` columns. The generated SQL referred to a nonexistent `eye_colour` table and was rejected before execution. B4 had complete evidence and a correct separately recorded response for this task.

## Missing set metadata with semantic mismatch: task 414

The reranked pack selected `set_translations` but omitted the `sets` table, including `sets.baseSetSize`, `sets.block`, and `sets.code`. The generated query treated the translation text as the card-count condition and executed with a non-equivalent result. B2 and B3 had separately recorded correct responses.

## Complete evidence but semantic mismatch: task 244

The selected pack contained all reference tables and columns for identifying the molecule with the most double bonds and checking its label. The candidate executed successfully but was not equivalent under `bird-execution-v1`. Full identifier recall cannot guarantee the intended logic or returned value semantics.

## Complete evidence with validator rejection: task 218

The pack exposed the molecule, atom, label, element, and join identifiers needed by the question. The candidate used a correlated CTE query, but the validator reported an unknown qualifier and prevented execution. This is retained as a policy rejection; complete schema evidence does not imply validator acceptance.

## Retrieval miss with incorrect direct join: task 1464

The pack exposed `income` and selected member name fields but omitted the reference `attendance` and `event` path. The generated query joined income directly to member and produced a semantic mismatch. The missing identifiers are recorded after generation and were unavailable to reranking.

## Interpretation limits

- The manifest contains 20 tasks and cannot support broad benchmark or significance claims.
- Hosted outputs are not claimed deterministic; comparisons retain each run's recorded response.
- Reference SQL is consulted only after generation to label identifier coverage and execution equivalence.
- A retrieval miss does not by itself explain an abstention, rejection, or semantic mismatch.
- A full-recall pack may still contain distractors or omit values and task semantics needed for a correct query.
- The cross-encoder was trained for English passage ranking rather than schema retrieval.
- The single frozen smoke outcome was not used to tune candidate depth, scoring, thresholds, or prompts.
