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
    DEFAULT_CUTOFF_DATE,
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
DEFAULT_RECENT_DAYS = 90
DEFAULT_FUTURE_END_DATE = "2027-01-01"
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


def _annotate_metrics(
    metrics: pd.DataFrame,
    name: str,
    train: pd.Series,
    test: pd.Series,
) -> pd.DataFrame:
    result = metrics.copy()
    result.insert(0, "series", name)
    result["train_start"] = _iso_date(train.index.min())
    result["train_end"] = _iso_date(train.index.max())
    result["test_start"] = _iso_date(test.index.min())
    result["test_end"] = _iso_date(test.index.max())
    return result[METRIC_COLUMNS]


def _prediction_rows(
    name: str,
    actual: pd.Series,
    predictions: dict[str, pd.Series],
    split: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model_name, forecast in predictions.items():
        joined = pd.concat(
            [actual.rename("actual"), pd.Series(forecast).rename("predicted")],
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
                    "split": split,
                }
            )
    return pd.DataFrame(rows, columns=PREDICTION_COLUMNS)


def _future_horizon(series: pd.Series, args: argparse.Namespace) -> int:
    if args.future_horizon is not None:
        return int(args.future_horizon)
    last_date = series.index.max()
    end_date = pd.Timestamp(args.future_end_date)
    if end_date <= last_date:
        raise ValueError(
            f"future-end-date {end_date.date()} must be after the series end "
            f"{last_date.date()}"
        )
    return len(pd.date_range(last_date + pd.Timedelta(days=1), end_date, freq="D"))


def forecast_series(
    name: str,
    series: pd.Series,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Forecast one series: full post-cutoff test, recent holdout and future."""
    cutoff_date = None if args.test_days is not None else getattr(args, "cutoff_date", None)
    train, test = time_based_split(
        series,
        test_days=args.test_days if args.test_days is not None else DEFAULT_TEST_DAYS,
        cutoff_date=cutoff_date,
    )
    horizon = len(test) if cutoff_date else min(args.horizon, len(test))
    if not cutoff_date and horizon < args.horizon:
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
    metrics = _annotate_metrics(metrics, name, train, test)
    test_frame = _prediction_rows(name, test, predictions, "test")

    recent_train, recent_test = time_based_split(
        series, test_days=args.recent_days
    )
    recent_metrics, recent_predictions = benchmark(
        _make_models(args),
        actual=recent_test,
        train=recent_train,
        horizon=len(recent_test),
        return_predictions=True,
    )
    recent_metrics = _annotate_metrics(
        recent_metrics, name, recent_train, recent_test
    )
    recent_frame = _prediction_rows(
        name, recent_test, recent_predictions, "recent"
    )

    future_horizon = _future_horizon(series, args)
    future_predictions = future_forecast(_make_models(args), series, future_horizon)
    future_reference = next(iter(future_predictions.values()))
    future_rows: list[dict[str, object]] = []
    for model_name, forecast in future_predictions.items():
        future_series = pd.Series(forecast).dropna()
        for date, value in future_series.items():
            future_rows.append(
                {
                    "series": name,
                    "date": _iso_date(date),
                    "actual": None,
                    "predicted": float(value),
                    "model": model_name,
                    "split": "future",
                }
            )
    future_frame = pd.DataFrame(future_rows, columns=PREDICTION_COLUMNS)
    prediction_frame = pd.concat([test_frame, future_frame], ignore_index=True)

    info = {
        "name": name,
        "observations": len(series),
        "train_start": _iso_date(train.index.min()),
        "train_end": _iso_date(train.index.max()),
        "test_start": _iso_date(test.index.min()),
        "test_end": _iso_date(test.index.max()),
        "cutoff_date": _iso_date(cutoff_date),
        "horizon": horizon,
        "recent_start": _iso_date(recent_test.index.min()),
        "recent_end": _iso_date(recent_test.index.max()),
        "recent_days": len(recent_test),
        "future_start": _iso_date(future_reference.index.min()),
        "future_end": _iso_date(future_reference.index.max()),
        "future_horizon": future_horizon,
    }
    return metrics, prediction_frame, recent_metrics, recent_frame, info


def write_outputs(
    metrics: pd.DataFrame,
    prediction_frame: pd.DataFrame,
    recent_metrics: pd.DataFrame,
    recent_frame: pd.DataFrame,
) -> tuple[Path, Path, Path, Path, Path]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUTPUTS_DIR / "forecast_metrics.csv"
    predictions_path = OUTPUTS_DIR / "forecast_predictions.csv"
    future_path = OUTPUTS_DIR / "forecast_future.csv"
    recent_metrics_path = OUTPUTS_DIR / "forecast_recent_metrics.csv"
    recent_predictions_path = OUTPUTS_DIR / "forecast_recent_predictions.csv"
    metrics.to_csv(metrics_path, index=False, columns=METRIC_COLUMNS)
    prediction_frame.to_csv(
        predictions_path, index=False, columns=PREDICTION_COLUMNS
    )
    future_frame = prediction_frame[prediction_frame["split"] == "future"]
    future_frame.to_csv(future_path, index=False, columns=PREDICTION_COLUMNS)
    recent_metrics.to_csv(recent_metrics_path, index=False, columns=METRIC_COLUMNS)
    recent_frame.to_csv(
        recent_predictions_path, index=False, columns=PREDICTION_COLUMNS
    )
    return (
        metrics_path,
        predictions_path,
        future_path,
        recent_metrics_path,
        recent_predictions_path,
    )


def run(args: argparse.Namespace) -> None:
    frame, source = load_forecast_frame()
    selection_cutoff = None if args.test_days is not None else args.cutoff_date
    series_map, top_countries = build_forecast_series(
        frame,
        target_column=TARGET_COLUMN,
        top_n=args.top_n,
        cutoff_date=selection_cutoff,
    )

    metrics_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []
    recent_metrics_frames: list[pd.DataFrame] = []
    recent_prediction_frames: list[pd.DataFrame] = []
    infos: list[dict[str, object]] = []
    for name, series in series_map.items():
        metrics, predictions, recent_metrics, recent_predictions, info = forecast_series(
            name, series, args
        )
        metrics_frames.append(metrics)
        prediction_frames.append(predictions)
        recent_metrics_frames.append(recent_metrics)
        recent_prediction_frames.append(recent_predictions)
        infos.append(info)

    metrics = pd.concat(metrics_frames, ignore_index=True)
    prediction_frame = pd.concat(prediction_frames, ignore_index=True)
    recent_metrics = pd.concat(recent_metrics_frames, ignore_index=True)
    recent_predictions = pd.concat(recent_prediction_frames, ignore_index=True)
    (
        metrics_path,
        predictions_path,
        future_path,
        recent_metrics_path,
        recent_predictions_path,
    ) = write_outputs(metrics, prediction_frame, recent_metrics, recent_predictions)

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
            f"cutoff={info['cutoff_date']} | "
            f"test={info['test_start']}..{info['test_end']} | "
            f"horizon={info['horizon']} | "
            f"recent={info['recent_start']}..{info['recent_end']} | "
            f"future={info['future_start']}..{info['future_end']}"
        )

    recent_best = (
        recent_metrics.sort_values(["series", "mae"])
        .groupby("series", as_index=False)
        .head(1)
    )
    print("\nrecent holdout best model per series:")
    print(recent_best[["series", "model", "mae", "rmse"]].to_string(index=False))

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
    print(f"wrote: {recent_metrics_path}")
    print(f"wrote: {recent_predictions_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark COVID-19 global and top-country forecasts"
    )
    parser.add_argument(
        "--cutoff-date",
        default=DEFAULT_CUTOFF_DATE,
        help="Train up to this date and evaluate on the full period after it.",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=None,
        help="Legacy holdout length; overrides --cutoff-date when provided.",
    )
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument(
        "--future-end-date",
        default=DEFAULT_FUTURE_END_DATE,
        help="Generate future predictions through this date (default: 2027-01-01).",
    )
    parser.add_argument(
        "--future-horizon",
        type=int,
        default=None,
        help="Legacy fixed future horizon; overrides --future-end-date when provided.",
    )
    parser.add_argument("--recent-days", type=int, default=DEFAULT_RECENT_DAYS)
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
    except (FileNotFoundError, ValueError, KeyError, ImportError, RuntimeError) as exc:
        print(f"forecast failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
