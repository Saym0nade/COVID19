from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .config import DB_PATH, SCHEMA_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db(connection: sqlite3.Connection, schema_path: Path = SCHEMA_PATH) -> None:
    connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
    connection.commit()


def load_dataframe(
    frame: pd.DataFrame,
    table: str,
    connection: sqlite3.Connection,
    if_exists: str = "append",
) -> None:
    frame.to_sql(table, connection, if_exists=if_exists, index=False)
    connection.commit()


def run_query(
    query: str,
    connection: sqlite3.Connection,
    params: dict | tuple | None = None,
) -> pd.DataFrame:
    return pd.read_sql_query(query, connection, params=params)
