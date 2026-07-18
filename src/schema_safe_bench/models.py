"""Shared, serializable benchmark models."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model that rejects accidental schema drift."""

    model_config = ConfigDict(extra="forbid")


class BenchmarkTask(StrictModel):
    """Normalized public benchmark task."""

    task_id: str
    db_id: str
    question: str
    reference_sql: str
    evidence: str | None = None
    difficulty: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id", "db_id", "question", "reference_sql")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value.strip()


class TaskManifest(StrictModel):
    """Deterministic selection of benchmark task IDs."""

    dataset: str
    dataset_revision: str
    selection: str
    seed: int
    task_ids: list[str]

    @field_validator("task_ids")
    @classmethod
    def unique_task_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("manifest must contain at least one task")
        if len(value) != len(set(value)):
            raise ValueError("manifest task IDs must be unique")
        return value


class Column(StrictModel):
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    primary_key_position: int = 0


class ForeignKey(StrictModel):
    id: int
    sequence: int
    from_column: str
    to_table: str
    to_column: str
    on_update: str
    on_delete: str


class Table(StrictModel):
    name: str
    columns: list[Column]
    foreign_keys: list[ForeignKey] = Field(default_factory=list)


class Catalog(StrictModel):
    """SQLite schema catalog without table contents."""

    db_id: str
    database_path: str
    tables: list[Table]
    catalog_version: str = "1"

    @property
    def table_names(self) -> set[str]:
        return {table.name for table in self.tables}

    def columns_by_table(self) -> dict[str, set[str]]:
        return {table.name: {column.name for column in table.columns} for table in self.tables}

    @classmethod
    def with_relative_path(cls, *, path: Path, db_id: str, tables: list[Table]) -> "Catalog":
        return cls(db_id=db_id, database_path=path.name, tables=tables)


class ValidationIssue(StrictModel):
    code: str
    message: str
    identifier: str | None = None


class ValidationResult(StrictModel):
    status: Literal["valid", "invalid", "abstain"]
    normalized_sql: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    referenced_tables: list[str] = Field(default_factory=list)
    referenced_columns: list[str] = Field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.status == "valid" and self.normalized_sql is not None


class ExecutionLimits(StrictModel):
    row_limit: int = Field(default=1000, ge=1, le=100_000)
    vm_step_budget: int = Field(default=1_000_000, ge=1_000)
    progress_interval: int = Field(default=1_000, ge=1)


class ExecutionResult(StrictModel):
    status: Literal["success", "error", "interrupted", "rejected"]
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    truncated: bool = False
    elapsed_ms: float | None = None
    error_type: str | None = None
    error_message: str | None = None


class ResultComparison(StrictModel):
    equivalent: bool
    order_sensitive: bool
    reason: str
    policy: Literal["bird-execution-v1", "strict-v1"] = "bird-execution-v1"


class EvaluatorCompatibilityCase(StrictModel):
    name: str
    official_equivalent: bool
    project_equivalent: bool
    matched: bool


class EvaluatorSmokeCheck(StrictModel):
    task_id: str
    db_id: str
    official_execution_success: bool
    project_execution_success: bool
    official_equivalent: bool
    project_equivalent: bool
    matched: bool
    result_rows: int | None = None


class EvaluatorCompatibilityReport(StrictModel):
    official_repository: str
    official_repository_revision: str
    official_evaluator_revision: str
    evaluation_ex_sha256: str
    evaluation_utils_sha256: str
    comparison_policy: Literal["bird-execution-v1"] = "bird-execution-v1"
    edge_case_count: int
    edge_case_matches: int
    smoke_task_count: int
    smoke_task_matches: int
    mismatches: list[str] = Field(default_factory=list)
    edge_cases: list[EvaluatorCompatibilityCase]
    smoke_checks: list[EvaluatorSmokeCheck]


class SchemaDocument(StrictModel):
    document_id: str
    table_name: str
    column_name: str | None = None
    text: str


class RetrievalHit(StrictModel):
    document_id: str
    table_name: str
    column_name: str | None = None
    score: float
    rank: int
    component_scores: dict[str, float] = Field(default_factory=dict)
    component_ranks: dict[str, int] = Field(default_factory=dict)
    component_contributions: dict[str, float] = Field(default_factory=dict)


class SchemaPackTable(StrictModel):
    name: str
    columns: list[Column]


class SchemaPack(StrictModel):
    tables: list[SchemaPackTable]
    foreign_keys: list[str]
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    retrieval_metadata: "RetrievalMetadata | None" = None
    serialized: str


class RetrievalMetadata(StrictModel):
    policy_id: str
    strategy: Literal["dense", "hybrid"]
    top_k: int
    document_count: int
    similarity: Literal["cosine"]
    embedding_model_id: str
    embedding_model_revision: str
    embedding_dimension: int
    document_embeddings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_embedding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_library: str
    embedding_library_version: str
    embedding_dependencies: dict[str, str]
    device: Literal["cpu"]
    precision: Literal["float32"]
    normalize_embeddings: Literal[True]
    batch_size: int
    max_seq_length: int
    query_prefix: str
    deterministic_algorithms: Literal[True]
    torch_num_threads: int
    lexical_algorithm: Literal["rank_bm25.BM25Okapi"] | None = None
    rank_bm25_version: str | None = None
    bm25_k1: float | None = None
    bm25_b: float | None = None
    bm25_epsilon: float | None = None
    fusion_algorithm: Literal["weighted-reciprocal-rank-fusion"] | None = None
    fusion_candidate_depth: Literal["all_documents"] | None = None
    fusion_lexical_weight: float | None = None
    fusion_dense_weight: float | None = None
    fusion_rank_constant: int | None = None
    fusion_tie_break: Literal["fused_score_desc_document_id_asc"] | None = None


class SchemaEvidenceMetrics(StrictModel):
    required_tables: list[str]
    required_columns: list[str]
    selected_tables: list[str]
    selected_columns: list[str]
    missing_tables: list[str]
    missing_columns: list[str]
    table_true_positives: int
    column_true_positives: int
    table_recall: float
    table_precision: float
    column_recall: float
    column_precision: float
    combined_recall: float
    combined_precision: float


class PromptMessage(StrictModel):
    role: Literal["system", "user"]
    content: str


class GenerationRequest(StrictModel):
    messages: list[PromptMessage]
    model_name: str
    temperature: float = 0.0
    max_output_tokens: int = Field(default=1000, ge=1)
    prompt_version: str
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none"


class GenerationResponse(StrictModel):
    raw_output: str
    model_name: str
    requested_model_name: str | None = None
    provider: Literal["offline", "openai"] = "offline"
    endpoint: Literal["offline", "responses"] = "offline"
    status: Literal["offline", "completed", "incomplete", "failed"] = "offline"
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    request_elapsed_ms: float | None = None
    estimated_cost_usd: float | None = None
    replayed: bool = False


class GenerationRecord(StrictModel):
    task_id: str
    request_sha256: str
    response: GenerationResponse


class GenerationRecording(StrictModel):
    format_version: Literal["1"] = "1"
    provider: Literal["openai"] = "openai"
    requested_model_name: str
    records: list[GenerationRecord] = Field(default_factory=list)


class Prediction(StrictModel):
    task_id: str
    sql: str
    raw_output: str | None = None
    request_sha256: str | None = None
    generation: GenerationResponse | None = None
    schema_pack: SchemaPack | None = None


class AuditTrace(StrictModel):
    run_id: str
    task_id: str
    db_id: str
    method_id: str
    question: str
    candidate_sql: str
    raw_output: str
    request_sha256: str | None = None
    configuration_sha256: str | None = None
    software_revision: str | None = None
    schema_pack: SchemaPack | None = None
    schema_evidence: SchemaEvidenceMetrics | None = None
    generation: GenerationResponse | None = None
    repair_count: int = Field(default=0, ge=0, le=1)
    validation: ValidationResult
    execution: ExecutionResult
    reference_execution: ExecutionResult
    comparison: ResultComparison | None = None
    failure_label: str | None = None


class RunSummary(StrictModel):
    run_id: str
    method_id: str
    tasks: int
    correct: int
    abstained: int
    invalid: int
    execution_errors: int
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class SchemaEvidenceAggregate(StrictModel):
    tasks: int
    tasks_with_full_table_recall: int
    tasks_with_full_column_recall: int
    retrieval_misses: int
    macro_table_recall: float
    macro_table_precision: float
    macro_column_recall: float
    macro_column_precision: float
    macro_combined_recall: float
    macro_combined_precision: float
    micro_table_recall: float
    micro_table_precision: float
    micro_column_recall: float
    micro_column_precision: float


class SchemaEvidenceTask(StrictModel):
    task_id: str
    db_id: str
    evidence: SchemaEvidenceMetrics


class SchemaEvidenceReport(StrictModel):
    format_version: Literal["1"] = "1"
    policy: Literal["reference-sql-identifiers-v1"] = "reference-sql-identifiers-v1"
    source_trace_sha256: str
    run_id: str
    method_id: str
    configuration_sha256: str
    aggregate: SchemaEvidenceAggregate
    tasks: list[SchemaEvidenceTask]


class ComparedRunMetrics(StrictModel):
    run_id: str
    method_id: str
    configuration_sha256: str
    software_revisions: list[str]
    tasks: int
    correct: int
    accuracy: float
    abstained: int
    invalid: int
    execution_errors: int
    failure_categories: dict[str, int]
    schema_chars: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    schema_evidence: SchemaEvidenceAggregate | None = None


class PairedTaskOutcome(StrictModel):
    task_id: str
    baseline_outcome: str
    treatment_outcome: str
    correctness_change: Literal["improved", "regressed", "unchanged"]
    baseline_schema_chars: int
    treatment_schema_chars: int


class PairedRunComparison(StrictModel):
    format_version: Literal["1"] = "1"
    baseline: ComparedRunMetrics
    treatment: ComparedRunMetrics
    deltas: dict[str, float | int]
    context_truncated_tasks: int
    improved_task_ids: list[str]
    regressed_task_ids: list[str]
    unchanged_task_ids: list[str]
    paired_outcomes: list[PairedTaskOutcome]


class SmokeRunConfig(StrictModel):
    run_id: str
    method_id: str
    tasks_path: Path
    databases_root: Path
    manifest_path: Path
    predictions_path: Path
    output_path: Path
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)


class HostedModelConfig(StrictModel):
    provider: Literal["openai"] = "openai"
    model_name: Literal["gpt-5.6-luna"] = "gpt-5.6-luna"
    endpoint: Literal["responses"] = "responses"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none"
    max_output_tokens: int = Field(default=1000, ge=1, le=128_000)
    store: Literal[False] = False
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)


class SpendBudgetConfig(StrictModel):
    project_limit_usd: float = Field(default=95.0, gt=0, lt=100)
    run_limit_usd: float = Field(default=5.0, gt=0)
    ledger_path: Path = Path(".cache/schema-safe-bench/openai-spend.json")


class HostedSchemaContextConfig(StrictModel):
    strategy: Literal["full", "length_truncated", "bm25", "dense", "hybrid"]
    max_chars: int | None = Field(default=None, ge=64)
    top_k: int | None = Field(default=None, ge=1)
    k1: float | None = Field(default=None, gt=0)
    b: float | None = Field(default=None, ge=0, le=1)
    epsilon: float | None = Field(default=None, ge=0)
    candidate_depth: Literal["all_documents"] | None = None
    lexical_weight: float | None = Field(default=None, ge=0)
    dense_weight: float | None = Field(default=None, ge=0)
    rank_constant: int | None = Field(default=None, ge=1)
    policy_id: str | None = None
    embedding: "DenseEmbeddingConfig | None" = None

    @model_validator(mode="after")
    def validate_strategy(self) -> "HostedSchemaContextConfig":
        if self.strategy == "full":
            if (
                any(
                    value is not None
                    for value in (
                        self.max_chars,
                        self.top_k,
                        self.k1,
                        self.b,
                        self.epsilon,
                        self.candidate_depth,
                        self.lexical_weight,
                        self.dense_weight,
                        self.rank_constant,
                    )
                )
                or self.policy_id is not None
                or self.embedding is not None
            ):
                raise ValueError("full schema context cannot define selection settings")
            return self
        if self.strategy == "length_truncated":
            if self.max_chars is None or not self.policy_id:
                raise ValueError("length-truncated schema context requires max_chars and policy_id")
            if any(
                value is not None
                for value in (
                    self.top_k,
                    self.k1,
                    self.b,
                    self.epsilon,
                    self.candidate_depth,
                    self.lexical_weight,
                    self.dense_weight,
                    self.rank_constant,
                )
            ):
                raise ValueError("length-truncated schema context cannot define BM25 settings")
            if self.embedding is not None:
                raise ValueError("length-truncated schema context cannot define embeddings")
            return self
        if self.strategy == "bm25":
            if (
                self.max_chars is not None
                or self.embedding is not None
                or any(
                    value is not None
                    for value in (
                        self.candidate_depth,
                        self.lexical_weight,
                        self.dense_weight,
                        self.rank_constant,
                    )
                )
            ):
                raise ValueError("BM25 schema context cannot define dense or fusion settings")
            if any(value is None for value in (self.top_k, self.k1, self.b, self.epsilon)):
                raise ValueError("BM25 schema context requires top_k, k1, b, and epsilon")
            if not self.policy_id:
                raise ValueError("BM25 schema context requires policy_id")
            return self
        if self.strategy == "dense":
            if self.max_chars is not None:
                raise ValueError("dense schema context cannot define max_chars")
            if any(
                value is not None
                for value in (
                    self.k1,
                    self.b,
                    self.epsilon,
                    self.candidate_depth,
                    self.lexical_weight,
                    self.dense_weight,
                    self.rank_constant,
                )
            ):
                raise ValueError("dense schema context cannot define lexical or fusion settings")
            if self.top_k is None or not self.policy_id or self.embedding is None:
                raise ValueError("dense schema context requires top_k, policy_id, and embedding")
            return self
        if self.max_chars is not None:
            raise ValueError("hybrid schema context cannot define max_chars")
        required = (
            self.top_k,
            self.k1,
            self.b,
            self.epsilon,
            self.candidate_depth,
            self.lexical_weight,
            self.dense_weight,
            self.rank_constant,
        )
        if any(value is None for value in required) or not self.policy_id or self.embedding is None:
            raise ValueError("hybrid schema context requires lexical, dense, and fusion settings")
        assert self.lexical_weight is not None and self.dense_weight is not None
        if self.lexical_weight + self.dense_weight <= 0:
            raise ValueError("hybrid retrieval weights must have a positive sum")
        return self


class DenseEmbeddingConfig(StrictModel):
    model_id: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    cache_dir: Path = Path(".cache/schema-safe-bench/huggingface")
    query_prefix: str
    device: Literal["cpu"] = "cpu"
    precision: Literal["float32"] = "float32"
    normalize_embeddings: Literal[True] = True
    batch_size: int = Field(default=32, ge=1)
    max_seq_length: int = Field(default=512, ge=1)
    embedding_dimension: int = Field(default=384, ge=1)
    weights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokenizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deterministic_algorithms: Literal[True] = True
    torch_num_threads: int = Field(default=1, ge=1)
    trust_remote_code: Literal[False] = False
    local_files_only: Literal[True] = True

    @field_validator("model_id", "query_prefix")
    @classmethod
    def non_empty_embedding_setting(cls, value: str) -> str:
        if not value:
            raise ValueError("embedding setting must not be empty")
        return value


class HostedRunConfig(StrictModel):
    run_id: str
    method_id: Literal["B0", "B1", "B2", "B3", "B4"]
    tasks_path: Path
    databases_root: Path
    manifest_path: Path
    recording_path: Path
    output_path: Path
    schema_context: HostedSchemaContextConfig | None = None
    environment_path: Path = Path(".env")
    model: HostedModelConfig = Field(default_factory=HostedModelConfig)
    budget: SpendBudgetConfig = Field(default_factory=SpendBudgetConfig)
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)

    @model_validator(mode="after")
    def validate_method_context(self) -> "HostedRunConfig":
        if self.method_id == "B0":
            if self.schema_context and self.schema_context.strategy != "full":
                raise ValueError("B0 requires full schema context")
            return self
        if self.method_id == "B1" and (
            not self.schema_context or self.schema_context.strategy != "length_truncated"
        ):
            raise ValueError("B1 requires length-truncated schema context")
        if self.method_id == "B2" and (
            not self.schema_context or self.schema_context.strategy != "bm25"
        ):
            raise ValueError("B2 requires BM25 schema context")
        if self.method_id == "B3" and (
            not self.schema_context or self.schema_context.strategy != "dense"
        ):
            raise ValueError("B3 requires dense schema context")
        if self.method_id == "B4" and (
            not self.schema_context or self.schema_context.strategy != "hybrid"
        ):
            raise ValueError("B4 requires hybrid schema context")
        return self


class AssetTaskCheck(StrictModel):
    task_id: str
    db_id: str
    catalog_tables: int
    validation_status: Literal["valid", "invalid", "abstain"]
    execution_status: Literal["success", "error", "interrupted", "rejected"]
    truncated: bool
    issue_codes: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.validation_status == "valid" and self.execution_status == "success"


class AssetVerificationReport(StrictModel):
    dataset: str
    dataset_revision: str
    manifest_seed: int
    task_count: int
    database_count: int
    passed_tasks: int
    failed_tasks: int
    checks: list[AssetTaskCheck]
