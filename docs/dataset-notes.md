# Dataset Notes

## Primary source

SchemaSafeBench targets the public BIRD Mini-Dev SELECT-only task set. Upstream sources:

- [BIRD Mini-Dev repository](https://github.com/bird-bench/mini_dev)
- [BIRD Mini-Dev dataset](https://huggingface.co/datasets/birdsql/bird_mini_dev)
- [BIRD benchmark](https://bird-bench.github.io/)

The benchmark provides SQLite databases, natural-language questions, schema metadata, and reference SQL. Upstream evidence may inform task understanding only when the experiment configuration explicitly allows it; reference SQL and results always remain evaluator-only.

## Local data policy

- Store downloaded assets under `data/raw/`.
- Do not commit databases or full upstream dataset archives.
- Record the upstream source, dataset revision, checksums when available, and local preparation command.
- Keep SELECT-only and CRUD-oriented task sets separate.
- Commit only distributable synthetic fixtures and small metadata manifests.

## Optional stress source

Spider 2.0-Lite may be used as a separately labelled enterprise-context stress evaluation after the primary BIRD pipeline is reproducible. Its protocol and results must not be merged with BIRD aggregates.
