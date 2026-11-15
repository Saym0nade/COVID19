from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import CATALOG_COMPACT_PATH, MERGED_DATA_PATH, RAW_DATA_PATH
from src.data_pipeline import load_merged_data, save_merged_parquet


def main() -> None:
    frame = load_merged_data(legacy_path=RAW_DATA_PATH, catalog_path=CATALOG_COMPACT_PATH)
    path = save_merged_parquet(frame, MERGED_DATA_PATH)
    print(f"merged rows: {len(frame)}")
    print(f"merged columns: {len(frame.columns)}")
    print(f"merged path: {path}")
    print(f"merged size: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
