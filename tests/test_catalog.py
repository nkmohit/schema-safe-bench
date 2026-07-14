import json
from pathlib import Path

from schema_safe_bench.catalog import extract_catalog, write_catalog


def test_extract_catalog_includes_columns_and_foreign_keys(sample_database: Path) -> None:
    catalog = extract_catalog(sample_database, db_id="shop")

    assert catalog.table_names == {"customers", "orders"}
    assert catalog.columns_by_table()["orders"] == {"order_id", "customer_id", "amount"}
    orders = next(table for table in catalog.tables if table.name == "orders")
    assert orders.foreign_keys[0].to_table == "customers"
    assert orders.foreign_keys[0].from_column == "customer_id"
    assert catalog.database_path == "shop.sqlite"


def test_write_catalog_creates_stable_json(sample_database: Path, tmp_path: Path) -> None:
    output = tmp_path / "nested" / "catalog.json"
    write_catalog(extract_catalog(sample_database), output)

    payload = json.loads(output.read_text())
    assert payload["db_id"] == "shop"
    assert [table["name"] for table in payload["tables"]] == ["customers", "orders"]


def test_extract_catalog_requires_existing_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite"
    try:
        extract_catalog(missing)
    except FileNotFoundError as exc:
        assert exc.args[0] == missing
    else:
        raise AssertionError("missing database should fail")
