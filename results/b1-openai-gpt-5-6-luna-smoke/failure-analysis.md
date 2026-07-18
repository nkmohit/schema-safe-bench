# B1 Representative Failure Analysis

This analysis is descriptive evidence from the committed 20-task smoke traces. It does not use the cases to revise the prompt, truncation threshold, or outputs.

## Correctness regressions

### Task 47: required table removed

The question asks for schools opened in Alameda County under a particular district jurisdiction. B0 was correct with 1,759 schema characters. B1 exposed 954 characters containing only `frpm` and `satscores`; the required `schools` table was absent. The model returned `ABSTAIN`, changing a correct B0 result into a safe abstention.

### Task 1351: required join column removed

The question asks for Brent Thomason's major. B0 was correct with 1,180 schema characters. B1 retained the `major` and `member` tables but stopped within the `member` declaration before exposing `link_to_major`. The model returned `ABSTAIN`, again changing a correct result into a safe abstention.

## Retained successes

Task 1042 remained correct after the schema context fell from 5,564 to 998 characters because the retained `League` and `Match` declarations contained the identifiers needed for the query. Tasks 24, 740, and 800 also remained correct under shorter schema contexts. These cases show that a prefix can be sufficient when the required objects happen to occur before the ceiling, but the policy does not rank evidence by relevance.

## Validator catches

Task 116 lost the later `trans` table from the financial catalog. The response substituted the visible `order` table and referenced unavailable columns; the validator rejected it before execution. Task 637 similarly referenced an unavailable `value` column and was rejected. These are safety successes, not semantic-correctness gains.

## Controlled-comparison limitation

Five tasks had complete schemas below the ceiling, so their B0 and B1 request digests were identical. Four produced the same raw output category. Task 218 produced a different raw response on the fresh hosted call and moved from semantic mismatch to validator rejection even though its request digest was unchanged. This demonstrates provider nondeterminism and prevents attributing every paired outcome transition solely to schema truncation.

## Summary

B1 reduced aggregate schema context and provider token use, but it did not improve correctness in this smoke sample. The two correctness regressions are directly associated with missing required schema evidence, and no incorrect B0 task became correct under B1. The result supports proceeding to relevance-based retrieval rather than tuning this prefix policy from observed outcomes.
