"""Provider-free protocol freeze for the complete BIRD Mini-Dev evaluation."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import yaml

from schema_safe_bench.catalog import extract_catalog
from schema_safe_bench.datasets import (
    build_full_evaluation_population,
    find_database,
    write_full_evaluation_population,
)
from schema_safe_bench.generation import (
    load_recording,
    load_repair_recording,
    maximum_request_cost,
    request_sha256,
)
from schema_safe_bench.models import (
    AssetVerificationReport,
    AuditTrace,
    DatabaseAsset,
    DatabaseInventory,
    FullEvaluationFreezeConfig,
    FullEvaluationFreezeReport,
    FullEvaluationMethodCost,
    HostedRunConfig,
    RepairPolicyConfig,
)
from schema_safe_bench.prompting.sql import (
    PROMPT_VERSION,
    build_generation_request,
    build_repair_request,
)
from schema_safe_bench.retrieval import full_schema_pack, length_truncated_schema_pack


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_freeze_config(path: Path) -> FullEvaluationFreezeConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Full-evaluation freeze configuration must be a mapping")
    return FullEvaluationFreezeConfig.model_validate(payload)


def _load_hosted_run_config(path: Path) -> HostedRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hosted run configuration must be a mapping")
    return HostedRunConfig.model_validate(payload)


def _write_model(model: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = model.model_dump_json(indent=2)  # type: ignore[attr-defined]
    path.write_text(serialized + "\n", encoding="utf-8")


def _database_inventory(
    databases_root: Path, database_ids: list[str]
) -> tuple[DatabaseInventory, dict[str, object]]:
    root = databases_root.resolve(strict=True)
    assets: list[DatabaseAsset] = []
    catalogs: dict[str, object] = {}
    for db_id in database_ids:
        database = find_database(root, db_id)
        wal = Path(f"{database}-wal")
        if wal.exists() and wal.stat().st_size:
            raise ValueError(f"database {db_id!r} has a non-empty WAL and is not frozen")
        catalog = extract_catalog(database, db_id=db_id)
        catalogs[db_id] = catalog
        assets.append(
            DatabaseAsset(
                db_id=db_id,
                relative_path=database.relative_to(root).as_posix(),
                size_bytes=database.stat().st_size,
                sha256=file_sha256(database),
                catalog_sha256=_canonical_sha256(catalog.model_dump(mode="json")),
                wal_status="empty" if wal.exists() else "absent",
            )
        )
    payload = [asset.model_dump(mode="json") for asset in assets]
    return (
        DatabaseInventory(
            database_count=len(assets),
            databases=assets,
            inventory_sha256=_canonical_sha256(payload),
        ),
        catalogs,
    )


def _read_traces(path: Path) -> dict[str, AuditTrace]:
    traces = [
        AuditTrace.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {trace.task_id: trace for trace in traces}
    if len(by_id) != len(traces):
        raise ValueError(f"duplicate task IDs in reusable trace {path}")
    return by_id


def _verify_reusable_initial_responses(
    *,
    method_id: str,
    config: HostedRunConfig,
    recording_path: Path,
    trace_path: Path,
    tasks: dict[str, object],
    manifest_ids: set[str],
) -> set[str]:
    recording = load_recording(recording_path, model_name=config.model.model_name)
    records = {record.task_id: record for record in recording.records}
    traces = _read_traces(trace_path)
    if set(records) != set(traces) or not set(records) <= manifest_ids:
        raise ValueError(f"{method_id} reusable recording and trace populations do not match")
    for task_id, record in records.items():
        trace = traces[task_id]
        task = tasks[task_id]
        if trace.method_id != method_id or trace.schema_pack is None:
            raise ValueError(f"{method_id} reusable trace is missing its frozen schema pack")
        request = build_generation_request(
            question=task.question,  # type: ignore[attr-defined]
            schema_pack=trace.schema_pack,
            model_name=config.model.model_name,
            temperature=config.model.temperature,
            max_output_tokens=config.model.max_output_tokens,
            reasoning_effort=config.model.reasoning_effort,
        )
        digest = request_sha256(task_id, request)
        if digest != record.request_sha256 or digest != trace.request_sha256:
            raise ValueError(f"{method_id} reusable request digest drift for task {task_id!r}")
    return set(records)


def _method_reservation(
    config: HostedRunConfig,
    *,
    missing_ids: list[str],
    tasks: dict[str, object],
    catalogs: dict[str, object],
) -> Decimal:
    reservations: list[Decimal] = []
    for task_id in missing_ids:
        task = tasks[task_id]
        catalog = catalogs[task.db_id]  # type: ignore[attr-defined]
        if config.method_id == "B1":
            assert config.schema_context and config.schema_context.max_chars
            pack = length_truncated_schema_pack(
                catalog,
                max_chars=config.schema_context.max_chars,  # type: ignore[arg-type]
            )
        else:
            # Full catalog is exact for B0 and a safe prompt-size ceiling for B2-B5.
            pack = full_schema_pack(catalog)  # type: ignore[arg-type]
        request = build_generation_request(
            question=task.question,  # type: ignore[attr-defined]
            schema_pack=pack,
            model_name=config.model.model_name,
            temperature=config.model.temperature,
            max_output_tokens=config.model.max_output_tokens,
            reasoning_effort=config.model.reasoning_effort,
        )
        reservations.append(maximum_request_cost(request))
    return sum(reservations, Decimal("0"))


def _repair_reservation(
    config: HostedRunConfig,
    *,
    missing_ids: list[str],
    tasks: dict[str, object],
    catalogs: dict[str, object],
) -> Decimal:
    reservations: list[Decimal] = []
    for task_id in missing_ids:
        task = tasks[task_id]
        pack = full_schema_pack(catalogs[task.db_id])  # type: ignore[attr-defined,arg-type]
        request = build_repair_request(
            question=task.question,  # type: ignore[attr-defined]
            schema_pack=pack,
            rejected_sql="X" * 20_000,
            error="validation:conservative_error_ceiling(" + "X" * 20_000 + ")",
            model_name=config.model.model_name,
            temperature=config.model.temperature,
            max_output_tokens=config.model.max_output_tokens,
            reasoning_effort=config.model.reasoning_effort,
        )
        reservations.append(maximum_request_cost(request))
    return sum(reservations, Decimal("0"))


def freeze_full_evaluation(config: FullEvaluationFreezeConfig) -> FullEvaluationFreezeReport:
    """Regenerate and verify all freeze artifacts without importing a provider SDK."""
    provenance = json.loads(config.dataset_provenance_path.read_text(encoding="utf-8"))
    task_provenance = provenance["task_records"]
    if task_provenance["revision"] != config.dataset_revision:
        raise ValueError("dataset revision drifted from provenance")
    if file_sha256(config.tasks_path) != task_provenance["sha256"]:
        raise ValueError("task source digest drifted from provenance")

    manifest, exclusions, normalized_tasks = build_full_evaluation_population(
        config.tasks_path, dataset_revision=config.dataset_revision
    )
    write_full_evaluation_population(
        manifest,
        exclusions,
        manifest_path=config.manifest_path,
        exclusion_report_path=config.exclusion_report_path,
    )
    inventory, catalogs = _database_inventory(config.databases_root, manifest.database_ids)
    _write_model(inventory, config.database_inventory_path)
    asset_verification = AssetVerificationReport.model_validate_json(
        config.asset_verification_path.read_text(encoding="utf-8")
    )
    if (
        asset_verification.task_count != manifest.task_count
        or [check.task_id for check in asset_verification.checks] != manifest.task_ids
    ):
        raise ValueError("asset verification does not exactly match the full manifest")

    run_configs = [_load_hosted_run_config(path) for path in config.run_config_paths]
    by_method = {run.method_id: run for run in run_configs}
    if set(by_method) != {f"B{index}" for index in range(8)} or len(run_configs) != 8:
        raise ValueError("freeze requires exactly one B0-B7 full-evaluation configuration")
    if len({run.output_path for run in run_configs}) != 8:
        raise ValueError("full-evaluation output paths must be unique")
    if any(run.output_path.exists() for run in run_configs):
        raise FileExistsError("a frozen full-evaluation output path already exists")
    shared_controls = (
        "tasks_path",
        "databases_root",
        "manifest_path",
        "model",
        "budget",
        "execution",
    )
    baseline = by_method["B0"]
    for run in run_configs:
        for control in shared_controls:
            if getattr(run, control) != getattr(baseline, control):
                raise ValueError(f"{run.method_id} drifted on shared control {control}")
        if run.manifest_path != config.manifest_path:
            raise ValueError(f"{run.method_id} does not use the frozen full manifest")
        if run.method_id in {"B0", "B1", "B2", "B3", "B4", "B5"} and run.replay_source_paths != [
            config.reusable_recording_paths[run.method_id]
        ]:
            raise ValueError(f"{run.method_id} does not bind its reusable smoke recording")
    for method_id in ("B6", "B7"):
        reliability = by_method[method_id].reliability
        assert reliability is not None
        if reliability.first_pass_config_path != config.run_config_paths[4]:
            raise ValueError(f"{method_id} must reference the full B4 configuration")
    b6_policy = by_method["B6"].reliability
    assert isinstance(b6_policy, RepairPolicyConfig)
    if b6_policy.repair_replay_source_paths != [config.reusable_recording_paths["B6"]]:
        raise ValueError("B6 does not bind its reusable smoke repair recording")

    tasks = {task.task_id: task for task in normalized_tasks}
    manifest_ids = set(manifest.task_ids)
    plans: list[FullEvaluationMethodCost] = []
    unique_missing = 0
    total_reservation = Decimal("0")
    for method_id in [f"B{index}" for index in range(8)]:
        run = by_method[method_id]
        reusable: set[str] = set()
        missing_ids: list[str] = []
        reservation = Decimal("0")
        if method_id in {"B0", "B1", "B2", "B3", "B4", "B5"}:
            reusable = _verify_reusable_initial_responses(
                method_id=method_id,
                config=run,
                recording_path=config.reusable_recording_paths[method_id],
                trace_path=config.reusable_trace_paths[method_id],
                tasks=tasks,
                manifest_ids=manifest_ids,
            )
            missing_ids = [task_id for task_id in manifest.task_ids if task_id not in reusable]
            reservation = _method_reservation(
                run, missing_ids=missing_ids, tasks=tasks, catalogs=catalogs
            )
            basis = (
                "exact full-catalog ceiling"
                if method_id == "B0"
                else "exact 1000-character schema ceiling"
                if method_id == "B1"
                else "full-catalog ceiling for retrieval-selected schema"
            )
        elif method_id == "B6":
            policy = run.reliability
            assert isinstance(policy, RepairPolicyConfig)
            repairs = load_repair_recording(
                config.reusable_recording_paths[method_id], model_name=run.model.model_name
            )
            reusable = {record.task_id for record in repairs.records}
            if not reusable <= manifest_ids:
                raise ValueError("B6 reusable repair recording contains unexpected task IDs")
            missing_ids = [task_id for task_id in manifest.task_ids if task_id not in reusable]
            reservation = _repair_reservation(
                run, missing_ids=missing_ids, tasks=tasks, catalogs=catalogs
            )
            basis = "worst-case one repair for every task using full schema and bounded error text"
        else:
            reusable = set(_read_traces(config.reusable_trace_paths["B4"]))
            basis = "B7 makes no hosted request and reuses the B4 first pass"
        unique_missing += len(missing_ids)
        total_reservation += reservation
        run_limit = Decimal(str(run.budget.run_limit_usd))
        config_path = config.run_config_paths[int(method_id[1:])]
        plans.append(
            FullEvaluationMethodCost(
                method_id=method_id,
                config_path=config_path.as_posix(),
                config_sha256=file_sha256(config_path),
                reusable_responses=len(reusable),
                missing_request_upper_bound=len(missing_ids),
                reservation_usd=float(reservation),
                run_limit_usd=float(run_limit),
                within_run_limit=reservation <= run_limit,
                reservation_basis=basis,
            )
        )

    ledger_path = baseline.budget.ledger_path
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    spent = Decimal(str(ledger.get("spent_usd", "0")))
    project_limit = Decimal(str(baseline.budget.project_limit_usd))
    within_project = spent + total_reservation <= project_limit
    all_runs_fit = all(plan.within_run_limit for plan in plans)
    budget_blocked = not within_project or not all_runs_fit
    verification_blocked = asset_verification.failed_tasks > 0
    if budget_blocked and verification_blocked:
        protocol_status = "blocked_by_budget_and_verification"
    elif budget_blocked:
        protocol_status = "blocked_by_budget"
    elif verification_blocked:
        protocol_status = "blocked_by_verification"
    else:
        protocol_status = "frozen"
    failed_reference_ids = [
        check.task_id for check in asset_verification.checks if not check.passed
    ]
    report = FullEvaluationFreezeReport(
        protocol_status=protocol_status,
        dataset_provenance_sha256=file_sha256(config.dataset_provenance_path),
        database_archive_sha256=provenance["database_archive"]["sha256"],
        database_archive_size_bytes=provenance["database_archive"]["size_bytes"],
        manifest_sha256=file_sha256(config.manifest_path),
        exclusion_report_sha256=file_sha256(config.exclusion_report_path),
        database_inventory_sha256=file_sha256(config.database_inventory_path),
        evaluator_provenance_sha256=file_sha256(config.evaluator_provenance_path),
        asset_verification_sha256=file_sha256(config.asset_verification_path),
        prompt_version=PROMPT_VERSION,
        task_count=manifest.task_count,
        database_count=manifest.database_count,
        reference_tasks_passed=asset_verification.passed_tasks,
        reference_tasks_failed=asset_verification.failed_tasks,
        reference_failure_task_ids=failed_reference_ids,
        methods=plans,
        unique_missing_request_upper_bound=unique_missing,
        projected_reservation_usd=float(total_reservation),
        ledger_spent_usd=float(spent),
        project_limit_usd=float(project_limit),
        projected_balance_usd=float(project_limit - spent - total_reservation),
        within_project_limit=within_project,
        leakage_boundary=[
            "reference SQL and results are evaluator-only",
            "task evidence and evaluator labels are never model-visible",
            "equivalence outcomes and schema-evidence requirements cannot affect requests",
            "repair and abstention depend only on candidate validation and controlled execution",
        ],
        limitations=[
            "Expanded hosted execution is separate and is not authorized by this freeze.",
            "B2-B5 reservations use full catalogs as conservative schema-context ceilings.",
            "B6 reserves one repair for every unrecorded response regardless of eligibility.",
            "The frozen execution budget interrupts some reference queries; they remain included.",
        ],
    )
    _write_model(report, config.report_path)
    return report
