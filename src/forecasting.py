from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd
from scipy import stats


DEFAULT_TEST_DAYS = 90
DEFAULT_HORIZON = 30


def _clean_series(series: pd.Series) -> pd.Series:
    cleaned = pd.Series(series).astype(float)
    if cleaned.index.has_duplicates:
        cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
    return cleaned


def _future_index(series: pd.Series, horizon: int) -> pd.Index:
    if horizon <= 0:
        raise ValueError("horizon must be a positive integer")
    if series.empty:
        raise ValueError("cannot forecast an empty series")
    if isinstance(series.index, pd.DatetimeIndex):
        try:
            frequency = pd.infer_freq(series.index)
        except ValueError:
            frequency = None
        frequency = frequency or "D"
        offset = pd.tseries.frequencies.to_offset(frequency)
        start = series.index[-1] + offset
        return pd.date_range(start=start, periods=horizon, freq=frequency)
    return pd.RangeIndex(start=len(series), stop=len(series) + horizon)


def time_based_split(
    series: pd.Series,
    test_days: int = DEFAULT_TEST_DAYS,
) -> tuple[pd.Series, pd.Series]:
    """Split a series into past train data and the last ``test_days`` as test."""
    if test_days <= 0:
        raise ValueError("test_days must be a positive integer")

    cleaned = _clean_series(series).sort_index()
    if cleaned.empty:
        raise ValueError("cannot split an empty series")

    if isinstance(cleaned.index, pd.DatetimeIndex):
        cutoff = cleaned.index.max() - pd.Timedelta(days=test_days)
        train = cleaned[cleaned.index <= cutoff]
        test = cleaned[cleaned.index > cutoff]
    else:
        if len(cleaned) <= test_days:
            raise ValueError("series is too short for the requested test_days")
        train = cleaned.iloc[:-test_days]
        test = cleaned.iloc[-test_days:]

    if train.empty or test.empty:
        raise ValueError("series is too short for the requested test_days")
    return train, test


def naive_forecast(series: pd.Series, horizon: int) -> pd.Series:
    """Repeat the last observed value."""
    cleaned = _clean_series(series).dropna().sort_index()
    if cleaned.empty:
        raise ValueError("cannot forecast an empty series")
    predictions = np.full(horizon, cleaned.iloc[-1], dtype=float)
    return pd.Series(predictions, index=_future_index(cleaned, horizon))


def seasonal_naive_forecast(
    series: pd.Series,
    horizon: int,
    season_length: int = 7,
) -> pd.Series:
    """Repeat the last seasonal cycle."""
    if season_length <= 0:
        raise ValueError("season_length must be a positive integer")
    cleaned = _clean_series(series).dropna().sort_index()
    if cleaned.empty:
        raise ValueError("cannot forecast an empty series")
    pattern = cleaned.to_numpy()[-season_length:]
    predictions = np.resize(pattern.astype(float), horizon)
    return pd.Series(predictions, index=_future_index(cleaned, horizon))


def moving_average_forecast(
    series: pd.Series,
    horizon: int,
    window: int = 7,
) -> pd.Series:
    """Use the mean of the last ``window`` observations as a flat forecast."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    cleaned = _clean_series(series).dropna().sort_index()
    if cleaned.empty:
        raise ValueError("cannot forecast an empty series")
    level = float(cleaned.to_numpy()[-window:].mean())
    predictions = np.full(horizon, level, dtype=float)
    return pd.Series(predictions, index=_future_index(cleaned, horizon))


def linear_regression_forecast(series: pd.Series, horizon: int) -> pd.Series:
    """Fit a least-squares linear trend on time and extrapolate it."""
    cleaned = _clean_series(series).dropna().sort_index()
    if len(cleaned) < 2:
        return naive_forecast(cleaned, horizon)

    x = np.arange(len(cleaned), dtype=float)
    y = cleaned.to_numpy(dtype=float)
    fitted = stats.linregress(x, y)
    future_x = np.arange(len(cleaned), len(cleaned) + horizon, dtype=float)
    predictions = fitted.intercept + fitted.slope * future_x
    predictions = np.clip(predictions, 0.0, None)
    return pd.Series(predictions, index=_future_index(cleaned, horizon))


def _aligned_pairs(actual: pd.Series, predicted: pd.Series) -> pd.DataFrame:
    actual_series = pd.Series(actual).dropna()
    predicted_series = pd.Series(predicted).dropna()
    if actual_series.empty or predicted_series.empty:
        return pd.DataFrame(columns=["actual", "predicted"])

    joined = pd.concat(
        [actual_series.rename("actual"), predicted_series.rename("predicted")],
        axis=1,
        join="inner",
    ).dropna()
    if not joined.empty:
        return joined

    length = min(len(actual_series), len(predicted_series))
    return pd.DataFrame(
        {
            "actual": actual_series.to_numpy()[:length],
            "predicted": predicted_series.to_numpy()[:length],
        }
    )


def evaluate_mae(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute error, ignoring missing observations."""
    joined = _aligned_pairs(actual, predicted)
    if joined.empty:
        return float("nan")
    return float((joined["actual"] - joined["predicted"]).abs().mean())


def evaluate_rmse(actual: pd.Series, predicted: pd.Series) -> float:
    """Root mean squared error, ignoring missing observations."""
    joined = _aligned_pairs(actual, predicted)
    if joined.empty:
        return float("nan")
    errors = joined["actual"] - joined["predicted"]
    return float(np.sqrt(np.mean(np.square(errors))))


class ForecastModel:
    """Small adapter that gives a bare forecast function a fit/predict API."""

    def __init__(self, function: Callable[..., pd.Series], **kwargs: object) -> None:
        self.function = function
        self.kwargs = kwargs
        self._train: pd.Series | None = None

    def fit(self, train: pd.Series) -> "ForecastModel":
        self._train = _clean_series(train).sort_index()
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._train is None:
            raise ValueError("call fit() before predict()")
        return self.function(self._train, horizon, **self.kwargs)


def make_model(function: Callable[..., pd.Series], **kwargs: object) -> ForecastModel:
    """Wrap a forecast function for use with :func:`benchmark`."""
    return ForecastModel(function, **kwargs)


def benchmark(
    models: Mapping[str, object],
    actual: pd.Series,
    train: pd.Series | None = None,
    horizon: int | None = None,
    return_predictions: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Compare models by MAE/RMSE, fit time, predict time and peak memory.

    ``models`` maps a model name to either a :class:`ForecastModel` (or any
    object exposing ``fit``/``predict``) or a callable ``f(train, horizon)``.
    ``train`` and ``horizon`` are required for callables and for the usual
    fit/predict flow.
    """
    rows: list[dict[str, object]] = []
    predictions: dict[str, pd.Series] = {}

    for name, model in models.items():
        fit_seconds = 0.0
        predict_seconds = 0.0
        peak_memory_mb = float("nan")

        tracemalloc.start()
        try:
            if hasattr(model, "fit") and hasattr(model, "predict"):
                if train is None or horizon is None:
                    raise ValueError("train and horizon are required for fitted models")
                started = time.perf_counter()
                fitted = model.fit(train)
                fit_seconds = time.perf_counter() - started

                started = time.perf_counter()
                forecast = fitted.predict(horizon)
                predict_seconds = time.perf_counter() - started
            elif callable(model):
                if train is None or horizon is None:
                    raise ValueError("train and horizon are required for callable models")
                started = time.perf_counter()
                forecast = model(train, horizon)
                predict_seconds = time.perf_counter() - started
            else:
                raise TypeError(f"unsupported model object for {name!r}")

            _, peak = tracemalloc.get_traced_memory()
            peak_memory_mb = peak / (1024 * 1024)
        finally:
            tracemalloc.stop()

        forecast = pd.Series(forecast).astype(float)
        predictions[name] = forecast
        rows.append(
            {
                "model": name,
                "mae": evaluate_mae(actual, forecast),
                "rmse": evaluate_rmse(actual, forecast),
                "fit_seconds": fit_seconds,
                "predict_seconds": predict_seconds,
                "peak_memory_mb": peak_memory_mb,
            }
        )

    metrics = pd.DataFrame(rows)
    if return_predictions:
        return metrics, predictions
    return metrics
