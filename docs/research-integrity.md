# Research Integrity Checklist

Use this checklist before publishing any score, table, figure, or case study.

## Provenance

- [ ] Public dataset source and immutable revision are recorded.
- [ ] Dataset terms permit the published artifact.
- [ ] Task manifest and exclusions are committed.
- [ ] No proprietary code, schema, SQL, content, or derived metric is present.

## Leakage controls

- [ ] Reference SQL and reference results are evaluator-only.
- [ ] Prompt logs show exactly which schema pack and optional public evidence were supplied.
- [ ] Retrieval tuning did not use hidden evaluation answers.
- [ ] Repair receives only the original inputs, rejected candidate, and concise failure information.

## Comparability

- [ ] Paired methods use identical tasks, generator settings, execution policy, and evaluator.
- [ ] Intentional context changes are the only method-specific prompt differences.
- [ ] Random seeds and model revisions are recorded.
- [ ] Provider errors, abstentions, and excluded tasks remain visible in totals.

## Claims

- [ ] Every aggregate links to raw traces and aggregation code.
- [ ] Samples are labelled as samples rather than complete benchmark results.
- [ ] Negative and mixed findings are included.
- [ ] External score comparisons use matching dataset and evaluator protocols.
- [ ] Wording does not claim formal safety, eliminated hallucinations, or universal state-of-the-art performance.

## Manual review

- [ ] Successful, failed, repaired, abstained, and policy-rejected outputs were inspected.
- [ ] Aggregate calculations were independently checked.
- [ ] Public artifacts were scanned for secrets and private metadata.
