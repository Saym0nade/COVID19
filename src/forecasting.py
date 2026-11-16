from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd
from scipy import stats


DEFAULT_TEST_DAYS = 90
DEFAULT_HORIZON = 30
DEFAULT_TOP_N = 5
AGGREGATE_PREFIX = "OWID_"


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


def _prepare_target_frame(frame: pd.DataFrame, target_column: str) -> pd.DataFrame:
    if "date" not in frame.columns:
        raise KeyError("forecast data must contain a 'date' column")
    if target_column not in frame.columns:
        raise KeyError(f"forecast data must contain {target_column!r}")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data[target_column] = pd.to_numeric(data[target_column], errors="coerce")
    return data


def _country_mask(data: pd.DataFrame) -> pd.Series:
    iso_code = data.get("iso_code", pd.Series("", index=data.index)).astype("string")
    location = data.get("location", pd.Series("", index=data.index)).astype("string")
    iso = iso_code.fillna("")
    name = location.fillna("")
    return iso.ne("") & ~iso.str.startswith(AGGREGATE_PREFIX) & name.ne("World")


def top_countries_by_latest_total(
    frame: pd.DataFrame,
    total_column: str = "total_cases",
    top_n: int = DEFAULT_TOP_N,
) -> pd.DataFrame:
    """Return the top ``top_n`` countries by their latest cumulative total.

    Rows without an ISO code (for example ``Asia excl. China``), OWID
    aggregates and ``World`` are excluded so the result only contains real
    countries. Each country is represented by its latest non-null observation,
    which is robust when the very last date has gaps.
    """
    if top_n <= 0:
        raise ValueError("top_n must be a positive integer")
    if total_column not in frame.columns:
        raise KeyError(f"forecast data must contain {total_column!r}")

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data[total_column] = pd.to_numeric(data[total_column], errors="coerce")
    valid = data[
        _country_mask(data) & data["date"].notna() & data[total_column].notna()
    ].sort_values("date")
    if valid.empty:
        raise ValueError(f"no country-level {total_column!r} observations found")

    latest = valid.groupby("iso_code", as_index=False, sort=False).tail(1)
    latest = latest.sort_values(
        [total_column, "iso_code"], ascending=[False, True]
    ).head(top_n)
    columns = ["iso_code", total_column]
    if "location" in latest.columns:
        columns.insert(1, "location")
    return latest[columns].reset_index(drop=True)


def build_global_series(
    frame: pd.DataFrame,
    target_column: str = "new_cases_smoothed",
) -> pd.Series:
    """Aggregate all country rows by date into a global daily series."""
    data = _prepare_target_frame(frame, target_column)
    countries = data[_country_mask(data) & data[target_column].notna()]

    if countries.empty:
        location = data.get("location", pd.Series("", index=data.index))
        world = data[(location.astype("string").fillna("") == "World") & data[target_column].notna()]
        if world.empty:
            raise ValueError(f"no {target_column!r} observations to aggregate")
        series = world.groupby("date")[target_column].sum(min_count=1)
    else:
        series = countries.groupby("date")[target_column].sum(min_count=1)

    series = series.sort_index().dropna()
    series.index.name = "date"
    if series.empty:
        raise ValueError(f"global {target_column!r} series is empty")
    return series


def build_country_series(
    frame: pd.DataFrame,
    iso_code: str,
    target_column: str = "new_cases_smoothed",
) -> pd.Series:
    """Build one country's daily series, summing duplicate rows per date."""
    data = _prepare_target_frame(frame, target_column)
    if "iso_code" not in data.columns:
        raise KeyError("forecast data must contain an 'iso_code' column")

    subset = data[
        data["iso_code"].astype("string").eq(str(iso_code))
        & data[target_column].notna()
    ]
    if subset.empty:
        raise ValueError(f"no {target_column!r} observations for {iso_code!r}")

    series = subset.groupby("date")[target_column].sum(min_count=1)
    series = series.sort_index().dropna()
    series.index.name = "date"
    if series.empty:
        raise ValueError(f"{target_column!r} series for {iso_code!r} is empty")
    return series


def build_forecast_series(
    frame: pd.DataFrame,
    target_column: str = "new_cases_smoothed",
    top_n: int = DEFAULT_TOP_N,
) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Build the global series plus the top-N country series."""
    series: dict[str, pd.Series] = {
        "global": build_global_series(frame, target_column)
    }
    top = top_countries_by_latest_total(frame, top_n=top_n)
    for iso_code in top["iso_code"]:
        series[f"country:{iso_code}"] = build_country_series(
            frame, str(iso_code), target_column
        )
    return series, top


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
