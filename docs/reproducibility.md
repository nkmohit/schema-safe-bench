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
  --tasks data/raw/bird-minidev/mini_dev_data/mini_dev_sqlite.json
```

## Catalog and smoke run

```bash
uv run schema-safe-bench catalog build \
  --database data/raw/bird-minidev/mini_dev_data/dev_databases/<db_id>/<db_id>.sqlite \
  --output data/processed/catalogs/<db_id>.json

uv run schema-safe-bench run smoke --config configs/runs/smoke.yaml
```

Every run configuration declares a task manifest, method, seed, execution limits, prompt version, and generator settings. Outputs are JSONL traces plus a summary JSON. Local runs are ignored unless deliberately curated as small examples.

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

CI performs no network downloads and makes no model-provider calls.
