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
    DEFAULT_FUTURE_HORIZON,
    DEFAULT_HORIZON,
    DEFAULT_LSTM_EPOCHS,
    DEFAULT_LSTM_HIDDEN,
    DEFAULT_LSTM_LOOKBACK,
    DEFAULT_SEED,
    DEFAULT_TEST_DAYS,
    DEFAULT_TOP_N,
    HoltWintersForecastModel,
    LSTMForecastModel,
    benchmark,
    build_forecast_series,
    future_forecast,
    linear_regression_forecast,
    make_model,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
    time_based_split,
)

TARGET_COLUMN = "new_cases_smoothed"
REQUIRED_COLUMNS = ["date", "iso_code", "location", "total_cases", TARGET_COLUMN]
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


def _iso_date(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _make_models(args: argparse.Namespace) -> dict[str, object]:
    return {
        "naive": make_model(naive_forecast),
        "seasonal_naive": make_model(
            seasonal_naive_forecast, season_length=args.season_length
        ),
        "moving_average": make_model(moving_average_forecast, window=args.window),
        "linear_regression": make_model(linear_regression_forecast),
        "holt_winters": HoltWintersForecastModel(season_length=args.season_length),
        "lstm": LSTMForecastModel(
            lookback=args.lstm_lookback,
            hidden_size=args.lstm_hidden,
            epochs=args.lstm_epochs,
            seed=args.seed,
        ),
    }


def forecast_series(
    name: str,
    series: pd.Series,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Forecast one named series and return metrics, prediction rows and info."""
    train, test = time_based_split(series, test_days=args.test_days)
    horizon = min(args.horizon, len(test))
    if horizon < args.horizon:
        print(
            f"{name}: requested horizon {args.horizon} exceeds test window; "
            f"using {horizon}."
        )

    metrics, predictions = benchmark(
        _make_models(args),
        actual=test,
        train=train,
        horizon=horizon,
        return_predictions=True,
    )

    reference = next(iter(predictions.values()))
    evaluation_dates = test.index.intersection(reference.index)
    test_start = evaluation_dates.min() if len(evaluation_dates) else pd.NaT
    test_end = evaluation_dates.max() if len(evaluation_dates) else pd.NaT

    metrics.insert(0, "series", name)
    metrics["train_start"] = _iso_date(train.index.min())
    metrics["train_end"] = _iso_date(train.index.max())
    metrics["test_start"] = _iso_date(test_start)
    metrics["test_end"] = _iso_date(test_end)
    metrics = metrics[METRIC_COLUMNS]

    rows: list[dict[str, object]] = []
    for model_name, forecast in predictions.items():
        joined = pd.concat(
            [test.rename("actual"), pd.Series(forecast).rename("predicted")],
            axis=1,
            join="inner",
        ).dropna()
        for date, row in joined.iterrows():
            rows.append(
                {
                    "series": name,
                    "date": _iso_date(date),
                    "actual": float(row["actual"]),
                    "predicted": float(row["predicted"]),
                    "model": model_name,
                    "split": "test",
                }
            )

    future_horizon = int(args.future_horizon)
    future_predictions = future_forecast(_make_models(args), series, future_horizon)
    future_reference = next(iter(future_predictions.values()))
    for model_name, forecast in future_predictions.items():
        future_series = pd.Series(forecast).dropna()
        for date, value in future_series.items():
            rows.append(
                {
                    "series": name,
                    "date": _iso_date(date),
                    "actual": None,
                    "predicted": float(value),
                    "model": model_name,
                    "split": "future",
                }
            )

    info = {
        "name": name,
        "observations": len(series),
        "train_start": _iso_date(train.index.min()),
        "train_end": _iso_date(train.index.max()),
        "test_start": _iso_date(test_start),
        "test_end": _iso_date(test_end),
        "horizon": horizon,
        "future_start": _iso_date(future_reference.index.min()),
        "future_end": _iso_date(future_reference.index.max()),
        "future_horizon": future_horizon,
    }
    return metrics, pd.DataFrame(rows, columns=PREDICTION_COLUMNS), info


def write_outputs(
    metrics: pd.DataFrame,
    prediction_frame: pd.DataFrame,
) -> tuple[Path, Path, Path]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUTPUTS_DIR / "forecast_metrics.csv"
    predictions_path = OUTPUTS_DIR / "forecast_predictions.csv"
    future_path = OUTPUTS_DIR / "forecast_future.csv"
    metrics.to_csv(metrics_path, index=False, columns=METRIC_COLUMNS)
    prediction_frame.to_csv(
        predictions_path, index=False, columns=PREDICTION_COLUMNS
    )
    future_frame = prediction_frame[prediction_frame["split"] == "future"]
    future_frame.to_csv(future_path, index=False, columns=PREDICTION_COLUMNS)
    return metrics_path, predictions_path, future_path


def run(args: argparse.Namespace) -> None:
    frame, source = load_forecast_frame()
    series_map, top_countries = build_forecast_series(
        frame, target_column=TARGET_COLUMN, top_n=args.top_n
    )

    metrics_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []
    infos: list[dict[str, object]] = []
    for name, series in series_map.items():
        metrics, predictions, info = forecast_series(name, series, args)
        metrics_frames.append(metrics)
        prediction_frames.append(predictions)
        infos.append(info)

    metrics = pd.concat(metrics_frames, ignore_index=True)
    prediction_frame = pd.concat(prediction_frames, ignore_index=True)
    metrics_path, predictions_path, future_path = write_outputs(metrics, prediction_frame)

    print(f"source: {source}")
    if not top_countries.empty:
        origin = ", ".join(
            f"{row.iso_code}={row.total_cases:.0f}"
            for row in top_countries.itertuples(index=False)
        )
        print(f"top {len(top_countries)} countries by latest total_cases: {origin}")
    print(f"series forecast: {', '.join(series_map)}")

    for info in infos:
        print(
            f"{info['name']}: observations={info['observations']} | "
            f"train={info['train_start']}..{info['train_end']} | "
            f"test={info['test_start']}..{info['test_end']} | "
            f"horizon={info['horizon']} | "
            f"future={info['future_start']}..{info['future_end']}"
        )

    summary = metrics[
        ["series", "model", "mae", "rmse", "fit_seconds", "predict_seconds", "peak_memory_mb"]
    ].copy()
    summary["mae"] = summary["mae"].round(3)
    summary["rmse"] = summary["rmse"].round(3)
    summary["fit_seconds"] = summary["fit_seconds"].round(6)
    summary["predict_seconds"] = summary["predict_seconds"].round(6)
    summary["peak_memory_mb"] = summary["peak_memory_mb"].round(4)
    print(summary.to_string(index=False))

    best = metrics.sort_values("mae").iloc[0]
    print(
        f"best model by MAE overall: {best['model']} "
        f"on {best['series']} ({best['mae']:.3f})"
    )
    print(f"wrote: {metrics_path}")
    print(f"wrote: {predictions_path}")
    print(f"wrote: {future_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark COVID-19 global and top-country forecasts"
    )
    parser.add_argument("--test-days", type=int, default=DEFAULT_TEST_DAYS)
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument("--future-horizon", type=int, default=DEFAULT_FUTURE_HORIZON)
    parser.add_argument("--season-length", type=int, default=7)
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--lstm-lookback", type=int, default=DEFAULT_LSTM_LOOKBACK)
    parser.add_argument("--lstm-hidden", type=int, default=DEFAULT_LSTM_HIDDEN)
    parser.add_argument("--lstm-epochs", type=int, default=DEFAULT_LSTM_EPOCHS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    try:
        run(parse_args())
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"forecast failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
