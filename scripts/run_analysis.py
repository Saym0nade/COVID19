"""Run Phase 1 EDA / time-series analysis for the COVID-19 project.

Outputs:
    outputs/eda_summary.json
    outputs/outliers.csv
    outputs/correlation.csv
    outputs/timeseries.csv
    figures/correlation_heatmap.png
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import (  # noqa: E402
    add_derived_fields,
    correlation_matrix,
    descriptive_stats,
    detect_outliers_iqr,
    missing_report,
    outlier_summary,
)
from src.config import (  # noqa: E402
    CATALOG_SAMPLE_PATH,
    FIGURES_DIR,
    LEGACY_SAMPLE_PATH,
    MERGED_DATA_PATH,
    OUTPUTS_DIR,
    PROCESSED_DATA_PATH,
)
from src.timeseries import resample_series, rolling_average  # noqa: E402
from src.visuals import save_correlation_heatmap  # noqa: E402

GROUP_COLUMNS = ["iso_code", "location"]
FREQUENCY = "W"
WINDOWS = (7, 14, 28)
OUTLIER_COLUMNS = [
    "new_cases",
    "new_deaths",
    "new_cases_per_million",
    "people_vaccinated_per_hundred",
    "gdp_per_capita",
    "human_development_index",
]
CORRELATION_COLUMNS = [
    "new_cases_per_million",
    "new_deaths_per_million",
    "people_vaccinated_per_hundred",
    "people_fully_vaccinated_per_hundred",
    "gdp_per_capita",
    "human_development_index",
    "population_density",
    "median_age",
    "life_expectancy",
    "diabetes_prevalence",
    "stringency_index",
    "reproduction_rate",
    "positive_rate",
    "hospital_beds_per_thousand",
]


def load_dataset() -> tuple[pd.DataFrame, Path]:
    """Load merged parquet if present, otherwise fall back to sample CSV."""
    candidates = [
        (MERGED_DATA_PATH, "parquet"),
        (PROCESSED_DATA_PATH, "parquet"),
        (CATALOG_SAMPLE_PATH, "csv"),
        (LEGACY_SAMPLE_PATH, "csv"),
    ]
    errors: list[str] = []
    for path, kind in candidates:
        path = Path(path)
        try:
            if not path.exists():
                continue
            if kind == "parquet":
                frame = pd.read_parquet(path)
            else:
                frame = pd.read_csv(path, low_memory=False)
            print(f"Loaded {path} ({len(frame):,} rows x {frame.shape[1]} columns)")
            return frame, path
        except Exception as error:  # noqa: BLE001
            errors.append(f"{path}: {type(error).__name__}: {error}")
    raise FileNotFoundError(
        "No usable data file found. Tried:\n" + "\n".join(errors or ["(none)"])
    )


def _sanitize(value):
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, bool):
        return value
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def build_outliers(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [column for column in OUTLIER_COLUMNS if column in frame.columns]
    frames = [detect_outliers_iqr(frame, column) for column in columns]
    frames = [item for item in frames if not item.empty]
    if frames:
        outliers = pd.concat(frames, ignore_index=True)
    else:
        outliers = pd.DataFrame(
            columns=[
                "iso_code",
                "location",
                "date",
                "column",
                "value",
                "lower_bound",
                "upper_bound",
            ]
        )
    summary = outlier_summary(frame, columns)
    return outliers, summary


def build_correlations(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    available = [column for column in CORRELATION_COLUMNS if column in frame.columns]
    if len(available) < 2:
        numeric = frame.select_dtypes(include="number").columns.tolist()
        available = numeric[:12]
    if len(available) < 2:
        return pd.DataFrame(), pd.DataFrame(), available

    matrix = correlation_matrix(frame, columns=available, method="pearson")
    records = []
    labels = matrix.columns.tolist()
    for i, feature_1 in enumerate(labels):
        for j in range(i + 1, len(labels)):
            feature_2 = labels[j]
            correlation = matrix.iloc[i, j]
            if pd.isna(correlation):
                continue
            records.append(
                {
                    "feature_1": feature_1,
                    "feature_2": feature_2,
                    "correlation": float(correlation),
                }
            )
    return matrix, pd.DataFrame(records), available


def build_timeseries(frame: pd.DataFrame) -> pd.DataFrame:
    required = [column for column in GROUP_COLUMNS + ["date", "new_cases"] if column in frame]
    if "date" not in required or "new_cases" not in required:
        return pd.DataFrame(
            columns=[
                "iso_code",
                "location",
                "date",
                "frequency",
                "new_cases",
                "rolling_7",
                "rolling_14",
                "rolling_28",
            ]
        )

    groups = [column for column in GROUP_COLUMNS if column in frame.columns]
    core = frame[required].copy()
    core["date"] = pd.to_datetime(core["date"], errors="coerce")
    core["new_cases"] = pd.to_numeric(core["new_cases"], errors="coerce")
    core = core.dropna(subset=["date"])
    if groups:
        core = core.drop_duplicates(subset=groups + ["date"], keep="last")

    rolled = core
    for window in WINDOWS:
        rolled = rolling_average(
            rolled,
            value_column="new_cases",
            window=window,
            group_columns=groups,
            date_column="date",
        )

    weekly = resample_series(
        rolled,
        date_column="date",
        value_column="new_cases",
        frequency=FREQUENCY,
        group_columns=groups,
        agg="sum",
    )

    join_keys = groups + ["date"]
    for window in WINDOWS:
        column = f"rolling_{window}"
        part = resample_series(
            rolled,
            date_column="date",
            value_column=column,
            frequency=FREQUENCY,
            group_columns=groups,
            agg="last",
        )
        part = part.drop(columns=["frequency"])
        weekly = weekly.merge(part, on=join_keys, how="left")

    ordered = join_keys + ["frequency", "new_cases"] + [f"rolling_{w}" for w in WINDOWS]
    ordered = [column for column in ordered if column in weekly.columns]
    return weekly[ordered].sort_values(join_keys).reset_index(drop=True)


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        frame, source_path = load_dataset()
    except FileNotFoundError as error:
        print(f"ERROR: {error}")
        return 1

    frame = add_derived_fields(frame)

    missing = missing_report(frame)
    stats = descriptive_stats(frame)
    outliers, outlier_stats = build_outliers(frame)
    matrix, correlation_long, correlation_features = build_correlations(frame)
    timeseries = build_timeseries(frame)

    outliers_path = OUTPUTS_DIR / "outliers.csv"
    correlation_path = OUTPUTS_DIR / "correlation.csv"
    timeseries_path = OUTPUTS_DIR / "timeseries.csv"
    summary_path = OUTPUTS_DIR / "eda_summary.json"
    heatmap_path = FIGURES_DIR / "correlation_heatmap.png"

    outliers.to_csv(outliers_path, index=False)
    correlation_long.to_csv(correlation_path, index=False)
    timeseries.to_csv(timeseries_path, index=False)

    total_cells = int(frame.shape[0] * frame.shape[1])
    total_missing = int(frame.isna().sum().sum())
    summary = {
        "dataset": str(source_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(frame.shape[0]),
        "columns": int(frame.shape[1]),
        "missing_summary": {
            "total_cells": total_cells,
            "total_missing": total_missing,
            "missing_percent": (total_missing / total_cells * 100.0)
            if total_cells
            else 0.0,
            "columns": missing.to_dict(orient="records"),
        },
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "outliers_summary": outlier_stats.to_dict(orient="records"),
        "descriptive_stats": stats.to_dict(orient="records"),
        "correlation_features": correlation_features,
        "timeseries": {
            "frequency": FREQUENCY,
            "rows": int(timeseries.shape[0]),
            "windows": list(WINDOWS),
        },
    }
    summary_path.write_text(
        json.dumps(_sanitize(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    heatmap_written = None
    try:
        heatmap_written = save_correlation_heatmap(
            matrix,
            heatmap_path,
            title="COVID-19 feature correlations (Pearson)",
        )
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: could not save heatmap: {type(error).__name__}: {error}")

    print("")
    print(f"Dataset          : {source_path}")
    print(f"Shape            : {frame.shape[0]:,} rows x {frame.shape[1]} columns")
    print(
        "Missing cells    : "
        f"{total_missing:,}/{total_cells:,} ({summary['missing_summary']['missing_percent']:.2f}%)"
    )
    print(
        f"Outliers         : {len(outliers):,} rows across "
        f"{0 if outlier_stats.empty else len(outlier_stats)} columns -> {outliers_path}"
    )
    print(
        f"Correlation      : {len(correlation_features)} features, "
        f"{len(correlation_long):,} pairs -> {correlation_path}"
    )
    print(
        f"Time series      : {len(timeseries):,} rows at frequency '{FREQUENCY}' "
        f"-> {timeseries_path}"
    )
    print(f"EDA summary      : {summary_path}")
    print(f"Heatmap          : {heatmap_written or '(not generated)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
