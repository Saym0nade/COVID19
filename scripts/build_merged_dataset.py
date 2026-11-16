from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import (
    CATALOG_COMPACT_PATH,
    MERGED_DATA_PATH,
    OUTPUTS_DIR,
    RAW_DATA_PATH,
)
from src.data_pipeline import (
    build_data_profile,
    clean_data,
    load_merged_data,
    optimize_dtypes,
    save_data_profile,
    save_merged_parquet,
)

PROFILE_PATH = OUTPUTS_DIR / "data_profile.json"


def main() -> None:
    try:
        frame = load_merged_data(
            legacy_path=RAW_DATA_PATH, catalog_path=CATALOG_COMPACT_PATH
        )
    except FileNotFoundError as exc:
        print(f"Missing raw data: {exc}")
        raise SystemExit(1) from exc
    except (OSError, ValueError) as exc:
        print(f"Failed to load raw data: {exc}")
        raise SystemExit(1) from exc

    raw_memory_mb = frame.memory_usage(deep=True).sum() / 1_048_576
    raw_rows = len(frame)

    # Cleaning is limited to normalising dates/numerics and dropping duplicate
    # iso_code+date rows. Missing values are intentionally preserved.
    frame = clean_data(frame)
    frame = optimize_dtypes(frame)

    try:
        path = save_merged_parquet(frame, MERGED_DATA_PATH)
    except (OSError, ValueError) as exc:
        print(f"Failed to write parquet: {exc}")
        raise SystemExit(1) from exc

    profile = build_data_profile(frame)
    profile["raw_rows_before_cleaning"] = int(raw_rows)
    profile["memory_before_optimize_mb"] = round(float(raw_memory_mb), 2)
    try:
        profile_path = save_data_profile(profile, PROFILE_PATH)
    except OSError as exc:
        print(f"Failed to write data profile: {exc}")
        raise SystemExit(1) from exc

    print(f"merged rows: {len(frame)}")
    print(f"merged columns: {len(frame.columns)}")
    print(f"merged path: {path}")
    print(f"merged size: {path.stat().st_size} bytes")
    print(f"date range: {profile['date_min']} .. {profile['date_max']}")
    print(f"memory: {profile['memory_mb']} MB (before optimize: {profile['memory_before_optimize_mb']} MB)")
    print(f"profile path: {profile_path}")


if __name__ == "__main__":
    main()
