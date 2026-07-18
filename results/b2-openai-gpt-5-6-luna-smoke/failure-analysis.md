# B2 Representative Cases

These cases come directly from the committed trace. They illustrate observed behavior and do not assign causality from correlation alone.

## Correct with complete evidence: task 1351

The question asks for Brent Thomason's major. BM25 ranked `major.major_name`, the `major` table, both major identifiers, `member.link_to_major`, and the `member` table among its leading hits. The pack contained every reference identifier, and the generated join between `member` and `major` was execution-equivalent to the reference. B2 reduced this task's schema context from 1,180 B0 characters to 412.

## Correct paired improvement: task 414

The question asks for the translation languages of a 180-card Ravnica set. The retrieved pack contained all required identifiers from `set_translations` and `sets`; the generated query was correct. This task improved from a B0 semantic mismatch and a B1 abstention. A single smoke transition does not establish that retrieval caused the improvement.

## Retrieval miss with abstention: task 24

The question requires both `frpm` and `satscores`. The fixed 12-hit selection concentrated on meal-related `frpm` fields and admitted two `schools` columns, but omitted `satscores` and its required identifiers. The model returned `ABSTAIN`. B0 and B1 had complete schema evidence for this task and generated correct SQL.

## Zero-score tie behavior: task 800

The question asks for the percentage of superheroes with blue eyes. None of the schema-document tokens matched the question after the locked lexical normalization, so all selected scores were zero. Ascending document-ID tie-breaking filled the pack with early schema documents and omitted `superhero`. The model safely abstained. This case exposes a declared limitation of unstemmed fixed-count lexical retrieval.

## Complete evidence but semantic mismatch: task 1028

All reference tables and columns were prompt-visible, and the candidate executed successfully. It filtered `Match.season` with `2010`, while the benchmark question's season interpretation required different semantics. The result was not equivalent. Complete schema evidence is necessary for many tasks but is not sufficient for semantic correctness.

## Retrieval miss with validator rejection: task 1464

The pack included `income`, `event`, `budget`, and `expense` evidence but omitted `member`. The response joined `member` and referenced a fabricated `m.full_name`; the validator rejected that unknown column before execution. The missing reference identifiers and rejection coexist in the trace, but the report does not claim a proven causal chain.

## Value-blind lexical limitation: task 459

The question names two cards, but schema documents contain identifiers rather than database values. Every BM25 score was zero. Stable tie-breaking included `cards.convertedManaCost` and `cards.asciiName` but omitted the reference column `cards.name`; the executable response produced a semantic mismatch. This shows the boundary between schema retrieval and value grounding.

## Interpretation limits

- The manifest contains 20 tasks and cannot support broad benchmark or significance claims.
- Hosted outputs are not claimed deterministic; comparisons retain each run's recorded response.
- Reference SQL is consulted only after generation to label identifier coverage and execution equivalence.
- A retrieval miss does not by itself explain an abstention, rejection, or semantic mismatch.
- A full-recall pack may still contain many distractors or omit values and task semantics needed for a correct query.
