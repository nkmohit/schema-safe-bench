# Benchmark Data

Downloaded benchmark assets are intentionally excluded from Git.

## Expected BIRD Mini-Dev layout

```text
data/raw/bird-minidev/
├── mini_dev_sqlite.json
├── dev_databases/
│   └── <db_id>/
│       └── <db_id>.sqlite
└── dev_tables.json
```

Upstream releases may use different filenames. The CLI accepts explicit task and database paths so preparation does not depend on one archive layout.

Use the official [BIRD Mini-Dev repository](https://github.com/bird-bench/mini_dev) or [dataset page](https://huggingface.co/datasets/birdsql/bird_mini_dev), review its terms, and record the source revision. Do not commit the downloaded databases.

Only SELECT-only tasks belong in the primary protocol. Keep CRUD tasks in a separate local path and configuration.
