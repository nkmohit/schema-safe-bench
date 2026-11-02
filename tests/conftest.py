import sqlite3
from pathlib import Path

import pytest

_BIRD_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw" / "bird-minidev"
_DATABASE_SUFFIXES = {".sqlite", ".sqlite3", ".db"}


def _bird_databases_present(databases: Path) -> bool:
    if not databases.is_dir():
        return False
    return any(
        path.is_file() and path.suffix in _DATABASE_SUFFIXES for path in databases.rglob("*")
    )


@pytest.fixture
def bird_minidev_assets() -> Path:
    """Local BIRD Mini-Dev download. The public package is about 800 MB and is not committed."""
    tasks = _BIRD_ROOT / "mini_dev_sqlite.json"
    databases = _BIRD_ROOT / "dev_databases"
    if tasks.is_file() and _bird_databases_present(databases):
        return _BIRD_ROOT
    pytest.skip(
        "BIRD Mini-Dev raw assets are not available at data/raw/bird-minidev "
        "(mini_dev_sqlite.json and dev_databases). The public download is about 800 MB "
        "and is intentionally not committed."
    )


@pytest.fixture
def sample_database(tmp_path: Path) -> Path:
    path = tmp_path / "shop.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
        INSERT INTO customers VALUES (1, 'Asha'), (2, 'Ben');
        INSERT INTO orders VALUES (10, 1, 25.5), (11, 1, 10.0), (12, 2, 7.0);
        """
    )
    connection.close()
    return path
