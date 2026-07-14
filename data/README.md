# Benchmark Data

Downloaded benchmark assets are intentionally excluded from Git.

## Expected BIRD Mini-Dev layout

```text
data/raw/bird-minidev/
└── mini_dev_data/
    ├── mini_dev_sqlite.json
    ├── dev_databases/
    │   └── <db_id>/
    │       └── <db_id>.sqlite
    └── dev_tables.json
```

Upstream releases may use different filenames. The CLI accepts explicit task and database paths so preparation does not depend on one archive layout.

Use the official [BIRD Mini-Dev repository](https://github.com/bird-bench/mini_dev) or [dataset page](https://huggingface.co/datasets/birdsql/bird_mini_dev), review its terms, and record the source revision. Do not commit the downloaded databases.

The official project points new users to its complete package and documents the SQLite task file as `mini_dev_data/mini_dev_sqlite.json` with databases under `mini_dev_data/dev_databases/`. After downloading an upstream archive, verify and extract it without overwriting an existing dataset directory:

```bash
uv run python scripts/prepare_bird_minidev.py \
  --archive /path/to/official-package.zip \
  --sha256 <verified-sha256> \
  --destination data/raw/bird-minidev
```

The preparation helper does not bypass upstream access controls, infer a mutable download URL, or redistribute the dataset. Record the source URL, source revision, and digest alongside local experiment metadata.

Only SELECT-only tasks belong in the primary protocol. Keep CRUD tasks in a separate local path and configuration.
