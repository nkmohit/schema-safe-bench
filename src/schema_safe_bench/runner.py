"""Config-driven offline and hosted smoke evaluation."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import find_database, load_bird_tasks
from schema_safe_bench.evaluation import compare_results
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
    RunSummary,
    SchemaPack,
    SmokeRunConfig,
    TaskManifest,
)
from schema_safe_bench.prompting import build_generation_request, extract_candidate_sql
from schema_safe_bench.reporting import write_run_artifacts
from schema_safe_bench.retrieval import full_schema_pack, length_truncated_schema_pack
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

    for task_id in manifest.task_ids:
        try:
            task = tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Manifest task {task_id!r} is absent from the dataset") from exc
        database = find_database(config.databases_root, task.db_id)
        catalog = extract_catalog(database, db_id=task.db_id)
        if config.method_id == "B0":
            schema_pack = full_schema_pack(catalog)
        else:
            assert config.schema_context and config.schema_context.max_chars
            schema_pack = length_truncated_schema_pack(
                catalog, max_chars=config.schema_context.max_chars
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
