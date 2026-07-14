"""Shared, serializable benchmark models."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SchemaPackTable(StrictModel):
    name: str
    columns: list[Column]


class SchemaPack(StrictModel):
    tables: list[SchemaPackTable]
    foreign_keys: list[str]
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    serialized: str


class PromptMessage(StrictModel):
    role: Literal["system", "user"]
    content: str


class GenerationRequest(StrictModel):
    messages: list[PromptMessage]
    model_name: str
    temperature: float = 0.0
    max_output_tokens: int = Field(default=1000, ge=1)
    prompt_version: str


class GenerationResponse(StrictModel):
    raw_output: str
    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_elapsed_ms: float | None = None


class Prediction(StrictModel):
    task_id: str
    sql: str
    raw_output: str | None = None


class AuditTrace(StrictModel):
    run_id: str
    task_id: str
    db_id: str
    method_id: str
    question: str
    candidate_sql: str
    raw_output: str
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


class SmokeRunConfig(StrictModel):
    run_id: str
    method_id: str
    tasks_path: Path
    databases_root: Path
    manifest_path: Path
    predictions_path: Path
    output_path: Path
    execution: ExecutionLimits = Field(default_factory=ExecutionLimits)


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
