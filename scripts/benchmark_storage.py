from __future__ import annotations

import json
import sys
import time
import tracemalloc
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import CORE_COLUMNS, OUTPUTS_DIR, PROCESSED_DIR, RAW_DATA_PATH

BENCHMARK_PATH = PROCESSED_DIR / "benchmark_legacy.parquet"
RESULT_PATH = OUTPUTS_DIR / "benchmark_data.json"


def _measure(func):
    tracemalloc.start()
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak / 1_048_576


def _file_mb(path: Path) -> float:
    return round(path.stat().st_size / 1_048_576, 2)


def main() -> None:
    if not RAW_DATA_PATH.exists():
        print(f"Raw CSV not found: {RAW_DATA_PATH}")
        raise SystemExit(1)

    print("Benchmark: CSV vs Parquet on the same legacy OWID data")
    print(f"source: {RAW_DATA_PATH}")
    print(f"columns: {len(CORE_COLUMNS)}")

    try:
        csv_frame, csv_seconds, csv_memory = _measure(
            lambda: pd.read_csv(RAW_DATA_PATH, usecols=CORE_COLUMNS, low_memory=False)
        )
    except (OSError, ValueError) as exc:
        print(f"Failed to read CSV: {exc}")
        raise SystemExit(1) from exc

    BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        csv_frame.to_parquet(BENCHMARK_PATH, index=False)
    except (OSError, ValueError) as exc:
        print(f"Failed to write benchmark parquet: {exc}")
        raise SystemExit(1) from exc

    try:
        parquet_frame, parquet_seconds, parquet_memory = _measure(
            lambda: pd.read_parquet(BENCHMARK_PATH, columns=CORE_COLUMNS).copy()
        )
    except (OSError, ValueError) as exc:
        print(f"Failed to read parquet: {exc}")
        raise SystemExit(1) from exc

    if set(csv_frame.columns) != set(parquet_frame.columns):
        print("CSV and Parquet reads produced different columns")
        raise SystemExit(1)
    parquet_frame = parquet_frame.loc[:, csv_frame.columns]

    speedup = csv_seconds / parquet_seconds if parquet_seconds > 0 else float("inf")
    summary = {
        "rows": int(len(csv_frame)),
        "columns": int(csv_frame.shape[1]),
        "csv_seconds": round(csv_seconds, 4),
        "parquet_seconds": round(parquet_seconds, 4),
        "csv_memory_mb": round(csv_memory, 2),
        "parquet_memory_mb": round(parquet_memory, 2),
        "csv_file_mb": _file_mb(RAW_DATA_PATH),
        "parquet_file_mb": _file_mb(BENCHMARK_PATH),
        "speedup": round(speedup, 2),
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"rows x columns: {summary['rows']} x {summary['columns']}")
    print(
        f"CSV:     {summary['csv_seconds']:.3f}s, "
        f"peak {summary['csv_memory_mb']:.2f} MB, "
        f"file {summary['csv_file_mb']:.2f} MB"
    )
    print(
        f"Parquet: {summary['parquet_seconds']:.3f}s, "
        f"peak {summary['parquet_memory_mb']:.2f} MB, "
        f"file {summary['parquet_file_mb']:.2f} MB"
    )
    print(f"speedup: {summary['speedup']:.2f}x")
    print(f"result: {RESULT_PATH}")


if __name__ == "__main__":
    main()
