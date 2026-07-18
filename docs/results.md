# Results

The repository publishes six hosted pipeline smoke artifacts over the same committed 20-task BIRD Mini-Dev manifest. They are not complete benchmark scores.

- B0 full schema: 6 correct, 2 safe abstentions, 10 semantic mismatches, and 2 bounded-execution interruptions.
- B1 length-truncated schema: 4 correct, 6 safe abstentions, 7 semantic mismatches, and 3 validator rejections.
- B2 BM25 schema retrieval: 2 correct, 10 safe abstentions, 6 semantic mismatches, and 2 validator rejections.
- B3 dense schema retrieval: 3 correct, 9 safe abstentions, 7 semantic mismatches, and 1 validator rejection.
- B4 hybrid schema retrieval: 3 correct, 6 safe abstentions, 9 semantic mismatches, 1 validator rejection, and 1 bounded-execution interruption.
- B5 hybrid plus reranking: 2 correct, 8 safe abstentions, 8 semantic mismatches, and 2 validator rejections.

The generated paired comparisons report configuration and implementation revisions, per-task transitions, schema context, evidence, token use, cost, and limitations. The B5 result links its comparisons against every earlier baseline. Every number resolves to a task manifest, locked configuration, raw trace set, exact response recording, and aggregation command.
