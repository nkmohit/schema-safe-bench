"""Config-driven offline and hosted smoke evaluation."""

import hashlib
import json
import os
import subprocess
from importlib.metadata import version
from pathlib import Path

import yaml

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import find_database, load_bird_tasks
from schema_safe_bench.evaluation import compare_results, evaluate_schema_evidence
from schema_safe_bench.execution import execute_read_only
from schema_safe_bench.generation import (
    OpenAIResponsesGenerator,
    SpendLedger,
    load_recording,
    maximum_request_cost,
    recorded_response,
    request_sha256,
    response_cost,
    save_record,
)
from schema_safe_bench.models import (
    AuditTrace,
    BenchmarkTask,
    Catalog,
    ExecutionLimits,
    GenerationRequest,
    GenerationResponse,
    HostedRunConfig,
    Prediction,
    RetrievalMetadata,
    RunSummary,
    SchemaPack,
    SmokeRunConfig,
    TaskManifest,
)
from schema_safe_bench.prompting import build_generation_request, extract_candidate_sql
from schema_safe_bench.reporting import write_run_artifacts
from schema_safe_bench.retrieval import (
    BM25Retriever,
    CrossEncoderReranker,
    DenseRetriever,
    HybridRetriever,
    SentenceTransformerEmbedder,
    build_schema_documents,
    build_schema_pack,
    full_schema_pack,
    length_truncated_schema_pack,
    rerank_hits,
)
from schema_safe_bench.validation import SqlValidator


def load_run_config(path: Path) -> SmokeRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Run configuration must be a mapping")
    return SmokeRunConfig.model_validate(payload)


def load_hosted_run_config(path: Path) -> HostedRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hosted run configuration must be a mapping")
    return HostedRunConfig.model_validate(payload)


def _load_predictions(path: Path) -> dict[str, Prediction]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = [
            {"task_id": task_id, "sql": value}
            if isinstance(value, str)
            else {"task_id": task_id, **value}
            for task_id, value in payload.items()
        ]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Predictions must be a task mapping or list")
    predictions = [Prediction.model_validate(record) for record in records]
    if len({prediction.task_id for prediction in predictions}) != len(predictions):
        raise ValueError("Prediction task IDs must be unique")
    return {prediction.task_id: prediction for prediction in predictions}


def _configuration_sha256(config: SmokeRunConfig | HostedRunConfig) -> str:
    encoded = json.dumps(
        config.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _software_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    revision = completed.stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
    ).stdout
    return f"{revision}+dirty" if dirty else revision


def _evaluate_prediction(
    *,
    run_id: str,
    method_id: str,
    configuration_sha256: str,
    software_revision: str,
    task: BenchmarkTask,
    prediction: Prediction,
    database: Path,
    catalog: Catalog,
    execution_limits: ExecutionLimits,
) -> AuditTrace:
    validator = SqlValidator(catalog)
    validation = validator.validate(prediction.sql)
    execution = execute_read_only(database, validation, limits=execution_limits)
    reference_validation = validator.validate(task.reference_sql)
    if not reference_validation.accepted:
        raise ValueError(f"Reference SQL failed validation for task {task.task_id!r}")
    reference_execution = execute_read_only(database, reference_validation, limits=execution_limits)
    schema_evidence = (
        evaluate_schema_evidence(reference_validation, prediction.schema_pack)
        if prediction.schema_pack
        else None
    )
    comparison = None
    failure_label = None
    if prediction.generation and prediction.generation.status not in {"offline", "completed"}:
        failure_label = f"provider_{prediction.generation.status}"
    elif validation.status == "abstain":
        failure_label = "safe_abstention"
    elif validation.status == "invalid":
        failure_label = "validator_rejection"
    elif execution.status != "success":
        failure_label = "execution_failure"
    else:
        comparison = compare_results(
            execution,
            reference_execution,
            policy="bird-execution-v1",
        )
        if not comparison.equivalent:
            failure_label = "semantic_mismatch"
    return AuditTrace(
        run_id=run_id,
        task_id=task.task_id,
        db_id=task.db_id,
        method_id=method_id,
        question=task.question,
        candidate_sql=prediction.sql,
        raw_output=prediction.raw_output or prediction.sql,
        request_sha256=prediction.request_sha256,
        configuration_sha256=configuration_sha256,
        software_revision=software_revision,
        schema_pack=prediction.schema_pack,
        schema_evidence=schema_evidence,
        generation=prediction.generation,
        validation=validation,
        execution=execution,
        reference_execution=reference_execution,
        comparison=comparison,
        failure_label=failure_label,
    )


def _summarize(run_id: str, method_id: str, traces: list[AuditTrace]) -> RunSummary:
    generations = [trace.generation for trace in traces if trace.generation]
    return RunSummary(
        run_id=run_id,
        method_id=method_id,
        tasks=len(traces),
        correct=sum(bool(trace.comparison and trace.comparison.equivalent) for trace in traces),
        abstained=sum(trace.validation.status == "abstain" for trace in traces),
        invalid=sum(trace.validation.status == "invalid" for trace in traces),
        execution_errors=sum(
            trace.execution.status in {"error", "interrupted"} for trace in traces
        ),
        input_tokens=sum(response.input_tokens or 0 for response in generations),
        output_tokens=sum(response.output_tokens or 0 for response in generations),
        estimated_cost_usd=round(
            sum(response.estimated_cost_usd or 0.0 for response in generations), 8
        ),
    )


def run_offline_smoke(config: SmokeRunConfig) -> tuple[list[AuditTrace], RunSummary]:
    tasks = {task.task_id: task for task in load_bird_tasks(config.tasks_path)}
    manifest = TaskManifest.model_validate_json(config.manifest_path.read_text(encoding="utf-8"))
    predictions = _load_predictions(config.predictions_path)
    configuration_sha256 = _configuration_sha256(config)
    software_revision = _software_revision()
    traces: list[AuditTrace] = []
    for task_id in manifest.task_ids:
        if task_id not in tasks:
            raise KeyError(f"Manifest task {task_id!r} is absent from the dataset")
        if task_id not in predictions:
            raise KeyError(f"Prediction for task {task_id!r} is missing")
        task = tasks[task_id]
        prediction = predictions[task_id]
        database = find_database(config.databases_root, task.db_id)
        traces.append(
            _evaluate_prediction(
                run_id=config.run_id,
                method_id=config.method_id,
                configuration_sha256=configuration_sha256,
                software_revision=software_revision,
                task=task,
                prediction=prediction,
                database=database,
                catalog=extract_catalog(database, db_id=task.db_id),
                execution_limits=config.execution,
            )
        )
    return traces, _summarize(config.run_id, config.method_id, traces)


def run_hosted_smoke(
    config: HostedRunConfig, *, replay_only: bool = False
) -> tuple[list[AuditTrace], RunSummary]:
    """Generate or replay hosted outputs, then evaluate them through the shared pipeline."""
    summary_path = config.output_path.with_suffix(".summary.json")
    if config.output_path.exists() or summary_path.exists():
        raise FileExistsError(f"Run output already exists: {config.output_path} or {summary_path}")
    tasks = {task.task_id: task for task in load_bird_tasks(config.tasks_path)}
    manifest = TaskManifest.model_validate_json(config.manifest_path.read_text(encoding="utf-8"))
    recording = load_recording(config.recording_path, model_name=config.model.model_name)
    configuration_sha256 = _configuration_sha256(config)
    software_revision = _software_revision()
    prepared: list[
        tuple[
            BenchmarkTask,
            Path,
            Catalog,
            SchemaPack,
            GenerationRequest,
            GenerationResponse | None,
            str,
        ]
    ] = []
    missing_reservations = []
    dense_embedder = None
    reranker = None
    dense_retrievers: dict[str, DenseRetriever] = {}
    if config.method_id in {"B3", "B4", "B5"}:
        assert config.schema_context and config.schema_context.embedding
        dense_embedder = SentenceTransformerEmbedder(config.schema_context.embedding)
    if config.method_id == "B5":
        assert config.schema_context and config.schema_context.reranker
        reranker = CrossEncoderReranker(config.schema_context.reranker)

    for task_id in manifest.task_ids:
        try:
            task = tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Manifest task {task_id!r} is absent from the dataset") from exc
        database = find_database(config.databases_root, task.db_id)
        catalog = extract_catalog(database, db_id=task.db_id)
        schema_pack = _hosted_schema_pack(
            config,
            catalog=catalog,
            question=task.question,
            dense_embedder=dense_embedder,
            dense_retrievers=dense_retrievers,
            reranker=reranker,
            configuration_sha256=configuration_sha256,
            software_revision=software_revision,
        )
        request = build_generation_request(
            question=task.question,
            schema_pack=schema_pack,
            model_name=config.model.model_name,
            temperature=config.model.temperature,
            max_output_tokens=config.model.max_output_tokens,
            reasoning_effort=config.model.reasoning_effort,
        )
        digest = request_sha256(task_id, request)
        replay = recorded_response(recording, task_id=task_id, expected_request_sha256=digest)
        if replay is None:
            missing_reservations.append(maximum_request_cost(request))
        prepared.append((task, database, catalog, schema_pack, request, replay, digest))

    if replay_only and missing_reservations:
        raise RuntimeError("replay-only run is missing recorded hosted responses")

    generator = None
    ledger = None
    if missing_reservations:
        try:
            from dotenv import load_dotenv
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "OpenAI support is not installed; run `uv sync --extra openai --dev`"
            ) from exc
        if os.name == "posix" and config.environment_path.exists():
            permissions = config.environment_path.stat().st_mode & 0o077
            if permissions:
                raise RuntimeError("environment file must be owner-only; run `chmod 600 .env`")
        load_dotenv(config.environment_path, override=False)
        ledger = SpendLedger(config.budget)
        ledger.authorize_run(missing_reservations)
        generator = OpenAIResponsesGenerator.from_environment(config.model)

    traces: list[AuditTrace] = []
    for task, database, catalog, schema_pack, request, replay, digest in prepared:
        response = replay
        if response is None:
            assert generator is not None and ledger is not None
            response = generator.generate(task.task_id, request)
            cost = response_cost(response)
            response = response.model_copy(update={"estimated_cost_usd": float(cost)})
            ledger.record(task_id=task.task_id, request_digest=digest, cost=cost)
            save_record(
                recording,
                config.recording_path,
                task_id=task.task_id,
                digest=digest,
                response=response,
            )
        candidate_sql = extract_candidate_sql(response.raw_output)
        prediction = Prediction(
            task_id=task.task_id,
            sql=candidate_sql,
            raw_output=response.raw_output,
            request_sha256=digest,
            generation=response,
            schema_pack=schema_pack,
        )
        traces.append(
            _evaluate_prediction(
                run_id=config.run_id,
                method_id=config.method_id,
                configuration_sha256=configuration_sha256,
                software_revision=software_revision,
                task=task,
                prediction=prediction,
                database=database,
                catalog=catalog,
                execution_limits=config.execution,
            )
        )
    return traces, _summarize(config.run_id, config.method_id, traces)


def _hosted_schema_pack(
    config: HostedRunConfig,
    *,
    catalog: Catalog,
    question: str,
    dense_embedder: SentenceTransformerEmbedder | None = None,
    dense_retrievers: dict[str, DenseRetriever] | None = None,
    reranker: CrossEncoderReranker | None = None,
    configuration_sha256: str | None = None,
    software_revision: str | None = None,
) -> SchemaPack:
    """Build prompt context from generation-safe inputs only."""
    if config.method_id == "B0":
        return full_schema_pack(catalog)
    assert config.schema_context is not None
    if config.method_id == "B1":
        assert config.schema_context.max_chars is not None
        return length_truncated_schema_pack(catalog, max_chars=config.schema_context.max_chars)
    assert config.schema_context.top_k is not None
    documents = build_schema_documents(catalog)
    if config.method_id == "B2":
        assert config.schema_context.k1 is not None
        assert config.schema_context.b is not None
        assert config.schema_context.epsilon is not None
        hits = BM25Retriever(
            documents,
            k1=config.schema_context.k1,
            b=config.schema_context.b,
            epsilon=config.schema_context.epsilon,
        ).retrieve(question, top_k=config.schema_context.top_k)
        return build_schema_pack(catalog, hits)

    embedding = config.schema_context.embedding
    assert embedding is not None and config.schema_context.policy_id is not None
    if dense_embedder is None:
        dense_embedder = SentenceTransformerEmbedder(embedding)
    retriever_cache = dense_retrievers if dense_retrievers is not None else {}
    catalog_key = hashlib.sha256(
        catalog.model_dump_json(exclude_none=True).encode("utf-8")
    ).hexdigest()
    retriever = retriever_cache.get(catalog_key)
    if retriever is None:
        retriever = DenseRetriever(
            documents,
            dense_embedder.embed_documents,
            embed_query=dense_embedder.embed_query,
        )
        retriever_cache[catalog_key] = retriever
    reranking_candidates = []
    if config.method_id == "B3":
        hits = retriever.retrieve(question, top_k=config.schema_context.top_k)
    else:
        assert config.schema_context.k1 is not None
        assert config.schema_context.b is not None
        assert config.schema_context.epsilon is not None
        assert config.schema_context.lexical_weight is not None
        assert config.schema_context.dense_weight is not None
        assert config.schema_context.rank_constant is not None
        hybrid = HybridRetriever(
            BM25Retriever(
                documents,
                k1=config.schema_context.k1,
                b=config.schema_context.b,
                epsilon=config.schema_context.epsilon,
            ),
            retriever,
            lexical_weight=config.schema_context.lexical_weight,
            dense_weight=config.schema_context.dense_weight,
            rank_constant=config.schema_context.rank_constant,
        )
        if config.method_id == "B5":
            assert config.schema_context.reranker_candidate_depth is not None
            assert config.schema_context.reranker is not None
            if reranker is None:
                reranker = CrossEncoderReranker(config.schema_context.reranker)
            first_stage_hits = hybrid.retrieve(
                question, top_k=config.schema_context.reranker_candidate_depth
            )
            hits, reranking_candidates = rerank_hits(
                question,
                documents,
                first_stage_hits,
                score=reranker.score,
                top_k=config.schema_context.top_k,
            )
        else:
            hits = hybrid.retrieve(question, top_k=config.schema_context.top_k)
    assert retriever.query_embedding_sha256 is not None
    pack = build_schema_pack(catalog, hits)
    reranker_config = config.schema_context.reranker
    return pack.model_copy(
        update={
            "reranking_candidates": reranking_candidates,
            "retrieval_metadata": RetrievalMetadata(
                policy_id=config.schema_context.policy_id,
                strategy=config.schema_context.strategy,
                top_k=config.schema_context.top_k,
                document_count=len(documents),
                similarity="cosine",
                embedding_model_id=embedding.model_id,
                embedding_model_revision=embedding.revision,
                embedding_dimension=embedding.embedding_dimension,
                document_embeddings_sha256=retriever.document_embeddings_sha256,
                query_embedding_sha256=retriever.query_embedding_sha256,
                embedding_library="sentence-transformers",
                embedding_library_version=dense_embedder.library_version,
                embedding_dependencies=dense_embedder.dependency_versions,
                device=embedding.device,
                precision=embedding.precision,
                normalize_embeddings=embedding.normalize_embeddings,
                batch_size=embedding.batch_size,
                max_seq_length=embedding.max_seq_length,
                query_prefix=embedding.query_prefix,
                deterministic_algorithms=embedding.deterministic_algorithms,
                torch_num_threads=embedding.torch_num_threads,
                lexical_algorithm=(
                    "rank_bm25.BM25Okapi" if config.method_id in {"B4", "B5"} else None
                ),
                rank_bm25_version=(
                    version("rank-bm25") if config.method_id in {"B4", "B5"} else None
                ),
                bm25_k1=config.schema_context.k1,
                bm25_b=config.schema_context.b,
                bm25_epsilon=config.schema_context.epsilon,
                fusion_algorithm=(
                    "weighted-reciprocal-rank-fusion" if config.method_id in {"B4", "B5"} else None
                ),
                fusion_candidate_depth=config.schema_context.candidate_depth,
                fusion_lexical_weight=config.schema_context.lexical_weight,
                fusion_dense_weight=config.schema_context.dense_weight,
                fusion_rank_constant=config.schema_context.rank_constant,
                fusion_tie_break=(
                    "fused_score_desc_document_id_asc" if config.method_id in {"B4", "B5"} else None
                ),
                reranker_candidate_depth=config.schema_context.reranker_candidate_depth,
                reranker_model_id=(reranker_config.model_id if reranker_config else None),
                reranker_model_revision=(reranker_config.revision if reranker_config else None),
                reranker_score_interpretation=(
                    reranker_config.score_interpretation if reranker_config else None
                ),
                reranker_pair_format=(reranker_config.pair_format if reranker_config else None),
                reranker_truncation=(reranker_config.truncation if reranker_config else None),
                reranker_batch_size=(reranker_config.batch_size if reranker_config else None),
                reranker_max_length=(reranker_config.max_length if reranker_config else None),
                reranker_tie_break=(
                    "score_desc_pre_rerank_rank_asc_document_id_asc" if reranker_config else None
                ),
                reranker_threshold=("none" if reranker_config else None),
                reranker_library=("sentence-transformers" if reranker_config else None),
                reranker_library_version=(
                    reranker.library_version if reranker_config and reranker else None
                ),
                reranker_dependencies=(
                    reranker.dependency_versions if reranker_config and reranker else None
                ),
                reranker_configuration_sha256=(configuration_sha256 if reranker_config else None),
                reranker_software_revision=(software_revision if reranker_config else None),
            ),
        }
    )


def run_and_write(config_path: Path) -> tuple[Path, Path]:
    config = load_run_config(config_path)
    traces, summary = run_offline_smoke(config)
    return write_run_artifacts(traces, summary, config.output_path)


def run_hosted_and_write(
    config_path: Path, *, replay_only: bool = False, output_path: Path | None = None
) -> tuple[Path, Path]:
    config = load_hosted_run_config(config_path)
    if output_path is not None:
        config = config.model_copy(update={"output_path": output_path})
    traces, summary = run_hosted_smoke(config, replay_only=replay_only)
    return write_run_artifacts(traces, summary, config.output_path)
