# Failure Analysis

Result reports use this taxonomy:

- retrieval miss: required schema evidence was absent;
- wrong table or column selection;
- missing or incorrect join;
- aggregation or grouping error;
- filter or value interpretation error;
- dialect or syntax error;
- validator rejection;
- execution interruption or failure;
- safe abstention;
- unexplained semantic mismatch.

Every published analysis should include representative successes, incorrect-but-executable queries, policy rejections, repair outcomes, abstentions, retrieval misses, multi-table cases, and cases where broader schema context beats retrieval. Cases must link to redacted public traces and identify the exact method configuration.

Do not infer a cause solely from result inequality. Inspect the question, selected schema pack, raw response, parsed SQL, validation findings, execution metadata, and reference behavior before assigning a label.
