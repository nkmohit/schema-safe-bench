"""Parser-backed SQLite read-query validation."""

from collections import defaultdict

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from schema_safe_bench.models import Catalog, ValidationIssue, ValidationResult

_BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile"}


class SqlValidator:
    """Validate one candidate against the read-only policy and real catalog."""

    def __init__(self, catalog: Catalog, *, max_query_length: int = 20_000) -> None:
        self.catalog = catalog
        self.max_query_length = max_query_length
        self._tables = {table.name.casefold(): table for table in catalog.tables}

    def validate(self, sql: str) -> ValidationResult:
        candidate = sql.strip()
        if candidate.upper() == "ABSTAIN":
            return ValidationResult(status="abstain")
        if not candidate:
            return self._invalid("empty_query", "Candidate SQL is empty")
        if len(candidate) > self.max_query_length:
            return self._invalid(
                "query_too_long", f"Query exceeds {self.max_query_length} characters"
            )
        try:
            statements = [statement for statement in parse(candidate, read="sqlite") if statement]
        except ParseError as exc:
            return self._invalid("parse_error", str(exc))
        if len(statements) != 1:
            return self._invalid("statement_count", "Exactly one SQL statement is required")

        statement = statements[0]
        if not isinstance(statement, exp.Query):
            return self._invalid(
                "non_read_query", "Only SELECT or read-only WITH queries are allowed"
            )

        issues: list[ValidationIssue] = []
        for function in statement.find_all(exp.Func):
            function_name = (
                function.name if isinstance(function, exp.Anonymous) else function.sql_name()
            ).casefold()
            if function_name in _BLOCKED_FUNCTIONS:
                issues.append(
                    ValidationIssue(
                        code="blocked_function",
                        message=f"Function {function_name!r} is blocked",
                        identifier=function_name,
                    )
                )

        cte_names = {
            cte.alias_or_name.casefold() for cte in statement.find_all(exp.CTE) if cte.alias_or_name
        }
        alias_to_table: dict[str, str] = {}
        referenced_tables: list[str] = []
        for table_ref in statement.find_all(exp.Table):
            name = table_ref.name
            if not name or name.casefold() in cte_names:
                continue
            table = self._tables.get(name.casefold())
            if table is None:
                issues.append(
                    ValidationIssue(
                        code="unknown_table",
                        message=f"Unknown table {name!r}",
                        identifier=name,
                    )
                )
                continue
            canonical = table.name
            referenced_tables.append(canonical)
            alias_to_table[canonical.casefold()] = canonical
            if table_ref.alias:
                alias_to_table[table_ref.alias.casefold()] = canonical

        available_columns: dict[str, set[str]] = defaultdict(set)
        for table_name in set(alias_to_table.values()):
            table = self._tables[table_name.casefold()]
            available_columns[table_name].update(column.name.casefold() for column in table.columns)

        virtual_columns = self._virtual_output_columns(statement)
        select_aliases = {
            expression.alias.casefold()
            for select in statement.find_all(exp.Select)
            for expression in select.expressions
            if expression.alias
        }
        referenced_columns: list[str] = []
        for column in statement.find_all(exp.Column):
            name = column.name
            if name == "*":
                continue
            qualifier = column.table.casefold() if column.table else None
            if qualifier in virtual_columns:
                if virtual_columns[qualifier] and name.casefold() not in virtual_columns[qualifier]:
                    issues.append(self._unknown_column(name, column.table))
                continue
            if qualifier:
                table_name = alias_to_table.get(qualifier)
                if table_name is None:
                    issues.append(
                        ValidationIssue(
                            code="unknown_qualifier",
                            message=f"Unknown table or alias {column.table!r}",
                            identifier=column.table,
                        )
                    )
                elif name.casefold() not in available_columns[table_name]:
                    issues.append(self._unknown_column(name, column.table))
                else:
                    referenced_columns.append(f"{table_name}.{name}")
            elif name.casefold() not in select_aliases:
                matching_tables = [
                    table_name
                    for table_name, names in available_columns.items()
                    if name.casefold() in names
                ]
                if not matching_tables and available_columns:
                    issues.append(self._unknown_column(name))
                else:
                    referenced_columns.extend(
                        f"{table_name}.{name}" for table_name in matching_tables
                    )

        if issues:
            return ValidationResult(
                status="invalid",
                issues=issues,
                referenced_tables=sorted(set(referenced_tables), key=str.casefold),
                referenced_columns=sorted(set(referenced_columns), key=str.casefold),
            )
        return ValidationResult(
            status="valid",
            normalized_sql=statement.sql(dialect="sqlite", pretty=False),
            referenced_tables=sorted(set(referenced_tables), key=str.casefold),
            referenced_columns=sorted(set(referenced_columns), key=str.casefold),
        )

    @staticmethod
    def _virtual_output_columns(statement: exp.Expression) -> dict[str, set[str]]:
        output: dict[str, set[str]] = {}
        for cte in statement.find_all(exp.CTE):
            name = cte.alias_or_name.casefold()
            explicit = {column.casefold() for column in cte.alias_column_names}
            if explicit:
                output[name] = explicit
                continue
            query = cte.this
            output[name] = {
                column.casefold() for column in query.named_selects if column and column != "*"
            }
        for subquery in statement.find_all(exp.Subquery):
            name = subquery.alias_or_name.casefold()
            if not name:
                continue
            explicit = {column.casefold() for column in subquery.alias_column_names}
            output[name] = explicit or {
                column.casefold()
                for column in subquery.this.named_selects
                if column and column != "*"
            }
        return output

    @staticmethod
    def _unknown_column(name: str, qualifier: str | None = None) -> ValidationIssue:
        identifier = f"{qualifier}.{name}" if qualifier else name
        return ValidationIssue(
            code="unknown_column",
            message=f"Unknown column {identifier!r}",
            identifier=identifier,
        )

    @staticmethod
    def _invalid(code: str, message: str) -> ValidationResult:
        return ValidationResult(
            status="invalid", issues=[ValidationIssue(code=code, message=message)]
        )
