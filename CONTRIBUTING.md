# Contributing

Contributions should preserve reproducibility, public-data provenance, and the separation between generation inputs and evaluation references.

## Set up

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Change requirements

- Add or update tests for behavioral changes.
- Keep CI independent of downloaded benchmark data and paid APIs.
- Version experiment configurations and prompt templates with behavior changes.
- Never expose reference SQL to a generator or repair prompt.
- Keep benchmark databases, credentials, provider responses containing sensitive data, and local result runs out of Git.
- Describe any task exclusions, evaluator changes, or result-affecting defaults explicitly.

Use focused commits that leave the repository executable and reviewable.
