import sqlite3
from pathlib import Path

import pytest


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
