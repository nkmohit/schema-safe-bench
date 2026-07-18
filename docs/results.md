# Results

The repository publishes two hosted pipeline smoke artifacts over the same committed 20-task BIRD Mini-Dev manifest. They are not complete benchmark scores.

- B0 full schema: 6 correct, 2 safe abstentions, 10 semantic mismatches, and 2 bounded-execution interruptions.
- B1 length-truncated schema: 4 correct, 6 safe abstentions, 7 semantic mismatches, and 3 validator rejections.

The generated [paired B0-versus-B1 comparison](../results/b0-vs-b1-openai-gpt-5-6-luna-smoke/README.md) reports configuration and implementation revisions, per-task transitions, schema context, token use, cost, and limitations. Every number resolves to a task manifest, locked configuration, raw trace set, exact response recording, and aggregation command.
