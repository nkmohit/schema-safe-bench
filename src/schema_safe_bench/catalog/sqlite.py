"""Read-only SQLite catalog extraction."""

import json
import sqlite3
from pathlib import Path

from schema_safe_bench.models import Catalog, Column, ForeignKey, Table


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def extract_catalog(path: Path, *, db_id: str | None = None) -> Catalog:
    """Extract tables, columns, primary keys, and foreign keys without row data."""
    with _connect_read_only(path) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
        tables: list[Table] = []
        for table_row in table_rows:
            name = str(table_row["name"])
            column_rows = connection.execute(
                "SELECT * FROM pragma_table_info(?)", (name,)
            ).fetchall()
            foreign_key_rows = connection.execute(
                "SELECT * FROM pragma_foreign_key_list(?)", (name,)
            ).fetchall()
            columns = [
                Column(
                    name=str(row["name"]),
                    data_type=str(row["type"] or ""),
                    nullable=not bool(row["notnull"]),
                    default=None if row["dflt_value"] is None else str(row["dflt_value"]),
                    primary_key_position=int(row["pk"]),
                )
                for row in column_rows
            ]
            foreign_keys = [
                ForeignKey(
                    id=int(row["id"]),
                    sequence=int(row["seq"]),
                    from_column=str(row["from"]),
                    to_table=str(row["table"]),
                    to_column=str(row["to"]),
                    on_update=str(row["on_update"]),
                    on_delete=str(row["on_delete"]),
                )
                for row in foreign_key_rows
            ]
            tables.append(Table(name=name, columns=columns, foreign_keys=foreign_keys))
    return Catalog.with_relative_path(path=path, db_id=db_id or path.stem, tables=tables)


def write_catalog(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(catalog.model_dump(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
