from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.config import (
    CATALOG_SAMPLE_PATH,
    LEGACY_SAMPLE_PATH,
    MERGED_DATA_PATH,
    OUTPUTS_DIR,
)
from src.forecasting import (
    DEFAULT_HORIZON,
    DEFAULT_TEST_DAYS,
    benchmark,
    linear_regression_forecast,
    make_model,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
    time_based_split,
)

TARGET_COLUMN = "new_cases_smoothed"
SERIES_NAME = "global_new_cases_smoothed"
REQUIRED_COLUMNS = ["date", "iso_code", "location", TARGET_COLUMN]
METRIC_COLUMNS = [
    "series",
    "model",
    "mae",
    "rmse",
    "fit_seconds",
    "predict_seconds",
    "peak_memory_mb",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
]
PREDICTION_COLUMNS = ["series", "date", "actual", "predicted", "model", "split"]


def _read_source(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return pd.read_csv(path, usecols=lambda column: column in REQUIRED_COLUMNS)


def load_forecast_frame() -> tuple[pd.DataFrame, str]:
    candidates = [
        (MERGED_DATA_PATH, "merged parquet"),
        (CATALOG_SAMPLE_PATH, "catalog sample"),
        (LEGACY_SAMPLE_PATH, "legacy sample"),
    ]
    errors: list[str] = []
    for path, label in candidates:
        try:
            frame = _read_source(path)
        except Exception as exc:  # missing file, read error, malformed data
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        if frame.empty:
            errors.append(f"{path}: empty dataset")
            continue
        return frame, f"{label} ({path})"
    raise FileNotFoundError("No usable forecast data found. Tried:\n" + "\n".join(errors))


def build_global_series(frame: pd.DataFrame) -> pd.Series:
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data[TARGET_COLUMN] = pd.to_numeric(data[TARGET_COLUMN], errors="coerce")

    iso_code = data.get("iso_code", pd.Series("", index=data.index)).astype("string")
    location = data.get("location", pd.Series("", index=data.index)).astype("string")

    is_aggregate = iso_code.fillna("").str.startswith("OWID_")
    is_world = location.fillna("") == "World"
    countries = data[~is_aggregate & ~is_world & data[TARGET_COLUMN].notna()]

    if countries.empty:
        world = data[is_world & data[TARGET_COLUMN].notna()]
        if world.empty:
            raise ValueError(f"no '{TARGET_COLUMN}' observations to aggregate")
        series = world.groupby("date")[TARGET_COLUMN].sum(min_count=1)
    else:
        series = countries.groupby("date")[TARGET_COLUMN].sum(min_count=1)

    series = series.sort_index().dropna()
    series.index.name = "date"
    if series.empty:
        raise ValueError(f"global '{TARGET_COLUMN}' series is empty")
    return series


def _iso_date(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def write_outputs(
    metrics: pd.DataFrame,
    predictions: dict[str, pd.Series],
    actual: pd.Series,
) -> tuple[Path, Path]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUTPUTS_DIR / "forecast_metrics.csv"
    predictions_path = OUTPUTS_DIR / "forecast_predictions.csv"

    prediction_rows: list[dict[str, object]] = []
    for model_name, forecast in predictions.items():
        joined = pd.concat(
            [actual.rename("actual"), pd.Series(forecast).rename("predicted")],
            axis=1,
            join="inner",
        ).dropna()
        for date, row in joined.iterrows():
            prediction_rows.append(
                {
                    "series": SERIES_NAME,
                    "date": _iso_date(date),
                    "actual": float(row["actual"]),
                    "predicted": float(row["predicted"]),
                    "model": model_name,
                    "split": "test",
                }
            )

    prediction_frame = pd.DataFrame(prediction_rows, columns=PREDICTION_COLUMNS)
    metrics.to_csv(metrics_path, index=False, columns=METRIC_COLUMNS)
    prediction_frame.to_csv(predictions_path, index=False, columns=PREDICTION_COLUMNS)
    return metrics_path, predictions_path


def run(args: argparse.Namespace) -> None:
    frame, source = load_forecast_frame()
    series = build_global_series(frame)
    train, test = time_based_split(series, test_days=args.test_days)

    horizon = min(args.horizon, len(test))
    if horizon < args.horizon:
        print(f"Requested horizon {args.horizon} exceeds test window; using {horizon}.")

    models = {
        "naive": make_model(naive_forecast),
        "seasonal_naive": make_model(
            seasonal_naive_forecast, season_length=args.season_length
        ),
        "moving_average": make_model(moving_average_forecast, window=args.window),
        "linear_regression": make_model(linear_regression_forecast),
    }

    metrics, predictions = benchmark(
        models,
        actual=test,
        train=train,
        horizon=horizon,
        return_predictions=True,
    )

    evaluation_dates = test.index.intersection(predictions["naive"].index)
    test_start = evaluation_dates.min() if len(evaluation_dates) else pd.NaT
    test_end = evaluation_dates.max() if len(evaluation_dates) else pd.NaT

    metrics.insert(0, "series", SERIES_NAME)
    metrics["train_start"] = _iso_date(train.index.min())
    metrics["train_end"] = _iso_date(train.index.max())
    metrics["test_start"] = _iso_date(test_start)
    metrics["test_end"] = _iso_date(test_end)
    metrics = metrics[["series", "model", "mae", "rmse", "fit_seconds", "predict_seconds", "peak_memory_mb", "train_start", "train_end", "test_start", "test_end"]]

    metrics_path, predictions_path = write_outputs(metrics, predictions, test)

    print(f"source: {source}")
    print(
        f"series: {SERIES_NAME} | observations: {len(series)} | "
        f"train: {_iso_date(train.index.min())}..{_iso_date(train.index.max())} | "
        f"test: {_iso_date(test_start)}..{_iso_date(test_end)} | horizon: {horizon}"
    )
    summary = metrics[
        ["model", "mae", "rmse", "fit_seconds", "predict_seconds", "peak_memory_mb"]
    ].copy()
    summary["mae"] = summary["mae"].round(3)
    summary["rmse"] = summary["rmse"].round(3)
    summary["fit_seconds"] = summary["fit_seconds"].round(6)
    summary["predict_seconds"] = summary["predict_seconds"].round(6)
    summary["peak_memory_mb"] = summary["peak_memory_mb"].round(4)
    print(summary.to_string(index=False))
    best = metrics.sort_values("mae").iloc[0]
    print(f"best model by MAE: {best['model']} ({best['mae']:.3f})")
    print(f"wrote: {metrics_path}")
    print(f"wrote: {predictions_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark COVID-19 global forecast baselines")
    parser.add_argument("--test-days", type=int, default=DEFAULT_TEST_DAYS)
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument("--season-length", type=int, default=7)
    parser.add_argument("--window", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    try:
        run(parse_args())
    except (FileNotFoundError, ValueError) as exc:
        print(f"forecast failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
