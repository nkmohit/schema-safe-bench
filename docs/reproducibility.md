# Reproducibility

## Environment

```bash
uv python install 3.12
uv sync --dev
uv run schema-safe-bench doctor
```

`uv.lock` is the dependency record used by CI. Provider credentials belong in a local `.env` or the process environment and must never be committed.

## Data preparation

Follow [data/README.md](../data/README.md), then validate paths and task parsing:

```bash
uv run schema-safe-bench dataset inspect \
  --tasks data/raw/bird-minidev/mini_dev_sqlite.json
```

## Catalog and smoke run

```bash
uv run schema-safe-bench catalog build \
  --database data/raw/bird-minidev/dev_databases/<db_id>/<db_id>.sqlite \
  --output data/processed/catalogs/<db_id>.json

uv run schema-safe-bench run smoke --config configs/runs/smoke.yaml
```

Before generation, verify that every manifest task can be cataloged and its reference SQL can be executed through the same safety boundary:

```bash
uv run schema-safe-bench dataset verify \
  --tasks data/raw/bird-minidev/mini_dev_sqlite.json \
  --databases data/raw/bird-minidev/dev_databases \
  --manifest data/processed/manifests/bird-minidev-select-smoke.json \
  --output data/processed/manifests/bird-minidev-select-smoke-verification.json
```

Every run configuration declares a task manifest, method, seed, execution limits, prompt version, and generator settings. Outputs are JSONL traces plus a summary JSON. Local runs are ignored unless deliberately curated as small examples.

For the hosted B0 through B6 paths, follow [hosted-generation.md](hosted-generation.md). The committed OpenAI/Luna configurations enforce local spend limits, record API usage without credentials, and support request-digest-checked offline replay. B3 through B5 additionally require the digest-verified local embedding snapshot; B5 also requires the digest-verified local cross-encoder snapshot. B6 reuses committed B4 schema packs and responses, so replay requires no embedding execution and validates the separate stage-bound repair recording.

Generate the paired comparison from committed traces with:

```bash
uv run schema-safe-bench results compare \
  --baseline results/b0-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --treatment results/b1-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --output results/local/b0-vs-b1-comparison.json
```

For B2 through B5, regenerate evaluator-only evidence before producing comparisons that include retrieval diagnostics:

```bash
for method in b0 b1 b2 b3 b4 b5; do
  uv run schema-safe-bench results schema-evidence \
    --trace results/${method}-openai-gpt-5-6-luna-smoke/trace.jsonl \
    --tasks data/raw/bird-minidev/mini_dev_sqlite.json \
    --databases data/raw/bird-minidev/dev_databases \
    --output results/local/schema-evidence/${method}.json
done

uv run schema-safe-bench results compare \
  --baseline results/b0-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --treatment results/b4-openai-gpt-5-6-luna-smoke/trace.jsonl \
  --baseline-evidence results/local/schema-evidence/b0.json \
  --treatment-evidence results/local/schema-evidence/b4.json \
  --output results/local/b0-vs-b4-comparison.json
```

## Evaluator compatibility

Clone and check out the revision recorded in [`data/provenance/bird-evaluator.json`](../data/provenance/bird-evaluator.json), then run:

```bash
uv run schema-safe-bench evaluation compatibility \
  --official-checkout /tmp/bird-mini-dev-evaluator \
  --tasks data/raw/bird-minidev/mini_dev_sqlite.json \
  --databases data/raw/bird-minidev/dev_databases \
  --manifest data/processed/manifests/bird-minidev-select-smoke.json \
  --output data/processed/manifests/bird-evaluator-compatibility.json
```

The command verifies upstream source checksums before comparing the declared semantic edge cases and smoke-manifest execution paths.

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

CI performs no network downloads and makes no model-provider calls.
