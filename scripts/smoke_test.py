from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_sql import DEFAULT_PARAMS, NAMED_PARAM, split_queries
from src.config import DB_PATH, MERGED_DATA_PATH, QUERIES_PATH

REQUIRED_PARQUET_COLUMNS = [
    "iso_code",
    "date",
    "location",
    "new_cases",
    "new_deaths",
    "people_vaccinated",
]
CORE_TABLES = ["countries", "covid_metrics", "vaccinations", "excess_mortality"]
OPTIONAL_TABLES = ["waves"]
RAW_TABLES = [*CORE_TABLES, *OPTIONAL_TABLES]

passed = 0
failed = 0
warnings = 0


def report(status: str, message: str) -> None:
    global passed, failed, warnings
    if status == "PASS":
        passed += 1
    elif status == "WARN":
        warnings += 1
    else:
        failed += 1
    print(f"[{status}] {message}")


def check_parquet() -> None:
    if not MERGED_DATA_PATH.exists():
        report("FAIL", f"merged parquet missing: {MERGED_DATA_PATH}")
        return
    try:
        columns = pq.read_schema(MERGED_DATA_PATH).names
    except (OSError, ValueError) as exc:
        report("FAIL", f"cannot read merged parquet schema: {exc}")
        return
    report("PASS", f"merged parquet present ({MERGED_DATA_PATH})")
    missing = [column for column in REQUIRED_PARQUET_COLUMNS if column not in columns]
    if missing:
        report("FAIL", f"merged parquet missing key columns: {missing}")
    else:
        report("PASS", f"merged parquet has key columns ({len(columns)} total)")


def check_database() -> None:
    if not DB_PATH.exists():
        report("FAIL", f"SQLite database missing: {DB_PATH}")
        return
    report("PASS", f"SQLite database present ({DB_PATH})")

    try:
        connection = sqlite3.connect(DB_PATH)
    except sqlite3.Error as exc:
        report("FAIL", f"cannot open SQLite database: {exc}")
        return

    try:
        for table in RAW_TABLES:
            try:
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error as exc:
                report("FAIL", f"table {table} missing or unreadable: {exc}")
                continue
            if table in OPTIONAL_TABLES:
                if count > 0:
                    report("PASS", f"table {table} present with {count} rows")
                else:
                    report(
                        "WARN",
                        f"table {table} present but empty "
                        "(wave detection is owned by the analysis participant)",
                    )
            elif count > 0:
                report("PASS", f"table {table} non-empty ({count} rows)")
            else:
                report("FAIL", f"table {table} is empty")
    finally:
        connection.close()


def check_queries() -> None:
    if not QUERIES_PATH.exists():
        report("FAIL", f"queries file missing: {QUERIES_PATH}")
        return
    if not DB_PATH.exists():
        report("FAIL", "cannot execute SQL queries without a database")
        return

    try:
        queries = split_queries(QUERIES_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        report("FAIL", f"cannot read queries file: {exc}")
        return

    if not queries:
        report("FAIL", "no queries found in queries.sql")
        return

    try:
        connection = sqlite3.connect(DB_PATH)
    except sqlite3.Error as exc:
        report("FAIL", f"cannot open SQLite database: {exc}")
        return

    try:
        for number, title, sql in queries:
            params = {
                name: DEFAULT_PARAMS[name]
                for name in NAMED_PARAM.findall(sql)
                if name in DEFAULT_PARAMS
            }
            try:
                frame = pd.read_sql_query(sql, connection, params=params or None)
            except (sqlite3.Error, pd.errors.DatabaseError, ValueError) as exc:
                report("FAIL", f"query_{number:02d} ({title}): {exc}")
                continue
            report(
                "PASS",
                f"query_{number:02d} ({title}): {len(frame)} rows x {len(frame.columns)} cols",
            )
    finally:
        connection.close()


def main() -> None:
    print("Smoke test: data artifacts, SQLite schema and SQL queries")
    print()

    check_parquet()
    check_database()
    check_queries()

    print()
    print(f"checks passed: {passed}, warnings: {warnings}, failed: {failed}")
    if failed:
        print("RESULT: FAIL")
        raise SystemExit(1)
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
