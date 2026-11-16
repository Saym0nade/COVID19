from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, OUTPUTS_DIR, QUERIES_PATH

SQL_OUTPUT_DIR = OUTPUTS_DIR / "sql"
DEFAULT_PARAMS = {"year": "2021", "region": None, "category": None}
QUERY_MARKER = re.compile(r"(?m)^--\s*(\d+)\.\s*(.*)$")
NAMED_PARAM = re.compile(r":([A-Za-z_]\w*)")


def split_queries(text: str) -> list[tuple[int, str, str]]:
    markers = list(QUERY_MARKER.finditer(text))
    queries: list[tuple[int, str, str]] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        sql = text[start:end].strip()
        if sql:
            queries.append((int(marker.group(1)), marker.group(2).strip(), sql))
    return queries


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}. Run scripts/build_sqlite.py first.")
        raise SystemExit(1)
    if not QUERIES_PATH.exists():
        print(f"Queries file not found: {QUERIES_PATH}")
        raise SystemExit(1)

    try:
        text = QUERIES_PATH.read_text(encoding="utf-8")
        queries = split_queries(text)
    except OSError as exc:
        print(f"Failed to read queries: {exc}")
        raise SystemExit(1) from exc

    if not queries:
        print("No queries found.")
        raise SystemExit(1)

    SQL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(DB_PATH)
    except sqlite3.Error as exc:
        print(f"Failed to open database: {exc}")
        raise SystemExit(1) from exc

    successes = 0
    failures: list[tuple[int, str]] = []
    try:
        for number, title, sql in queries:
            params = {}
            for name in NAMED_PARAM.findall(sql):
                if name in DEFAULT_PARAMS:
                    params[name] = DEFAULT_PARAMS[name]
            try:
                frame = pd.read_sql_query(sql, connection, params=params or None)
                output_path = SQL_OUTPUT_DIR / f"query_{number:02d}.csv"
                frame.to_csv(output_path, index=False)
                successes += 1
                print(f"query_{number:02d}: {len(frame)} rows x {len(frame.columns)} cols -> {output_path.name}")
            except (sqlite3.Error, pd.errors.DatabaseError, ValueError) as exc:
                failures.append((number, str(exc)))
                print(f"query_{number:02d}: FAILED ({exc})")
    finally:
        connection.close()

    print()
    print(f"queries executed: {len(queries)}")
    print(f"succeeded: {successes}")
    print(f"failed: {len(failures)}")
    for number, message in failures:
        print(f"  query_{number:02d}: {message}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
