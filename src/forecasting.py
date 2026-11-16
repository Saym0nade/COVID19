from __future__ import annotations

import time
import tracemalloc
import warnings
from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd
import torch
from scipy import stats
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from torch import nn


DEFAULT_TEST_DAYS = 90
DEFAULT_CUTOFF_DATE = "2023-12-31"
DEFAULT_HORIZON = 30
DEFAULT_FUTURE_HORIZON = 30
DEFAULT_TOP_N = 5
DEFAULT_SEED = 42
DEFAULT_LSTM_LOOKBACK = 30
DEFAULT_LSTM_HIDDEN = 32
DEFAULT_LSTM_EPOCHS = 40
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
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                frequency = pd.infer_freq(series.index)
        except ValueError:
            frequency = None
        frequency = getattr(frequency, "freqstr", frequency) or "D"
        offset = pd.tseries.frequencies.to_offset(frequency)
        start = series.index[-1] + offset
        return pd.date_range(start=start, periods=horizon, freq=frequency)
    return pd.RangeIndex(start=len(series), stop=len(series) + horizon)


def time_based_split(
    series: pd.Series,
    test_days: int = DEFAULT_TEST_DAYS,
    cutoff_date: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Split into train and the full period after a cutoff date."""
    cleaned = _clean_series(series).sort_index()
    if cleaned.empty:
        raise ValueError("cannot split an empty series")

    if cutoff_date is not None:
        if not isinstance(cleaned.index, pd.DatetimeIndex):
            raise ValueError("cutoff_date requires a DatetimeIndex")
        cutoff = pd.Timestamp(cutoff_date)
        train = cleaned[cleaned.index <= cutoff]
        test = cleaned[cleaned.index > cutoff]
        if train.empty or test.empty:
            raise ValueError(f"series has no observations around cutoff {cutoff.date()}")
        return train, test

    if test_days <= 0:
        raise ValueError("test_days must be a positive integer")
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
    target_column: str | None = None,
    min_target_date: str | pd.Timestamp | None = None,
    min_target_mean: float = 0.0,
    min_target_observations: int = 30,
) -> pd.DataFrame:
    """Return top countries by latest cumulative total.

    If ``target_column`` and ``min_target_date`` are given, only countries with
    enough non-zero target observations after that date are eligible. This keeps
    the post-2023 forecast comparison on countries that actually have data in
    the forecast window.
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

    if target_column and min_target_date and target_column in data.columns:
        target_values = pd.to_numeric(data[target_column], errors="coerce")
        recent = data[
            _country_mask(data)
            & (data["date"] > pd.Timestamp(min_target_date))
            & target_values.notna()
        ].copy()
        if not recent.empty:
            recent[target_column] = pd.to_numeric(recent[target_column], errors="coerce")
            stats = recent.groupby("iso_code")[target_column].agg(["mean", "count"])
            keep = stats[
                (stats["mean"] > min_target_mean)
                & (stats["count"] >= min_target_observations)
            ].index
            if len(keep) >= top_n:
                valid = valid[valid["iso_code"].isin(keep)]

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
    cutoff_date: str | pd.Timestamp | None = None,
) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Build the global series plus the top-N country series."""
    series: dict[str, pd.Series] = {
        "global": build_global_series(frame, target_column)
    }
    top = top_countries_by_latest_total(
        frame,
        top_n=top_n,
        target_column=target_column,
        min_target_date=cutoff_date,
    )
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


class HoltWintersForecastModel:
    """Library-provided Exponential Smoothing / Holt-Winters model."""

    def __init__(
        self,
        season_length: int = 7,
        trend: str = "add",
        seasonal: str = "add",
        damped_trend: bool = True,
    ) -> None:
        self.season_length = season_length
        self.trend = trend
        self.seasonal = seasonal
        self.damped_trend = damped_trend
        self._series: pd.Series | None = None
        self._model = None

    def fit(self, train: pd.Series) -> "HoltWintersForecastModel":
        cleaned = _clean_series(train).dropna().sort_index()
        self._series = cleaned
        self._model = None
        if len(cleaned) < max(4, self.season_length + 2):
            return self
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ExponentialSmoothing(
                    cleaned,
                    trend=self.trend,
                    damped_trend=self.damped_trend,
                    seasonal=self.seasonal if len(cleaned) >= 2 * self.season_length else None,
                    seasonal_periods=self.season_length if len(cleaned) >= 2 * self.season_length else None,
                    initialization_method="estimated",
                )
                self._model = model.fit(optimized=True)
        except (ValueError, TypeError, np.linalg.LinAlgError):
            self._model = None
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._series is None:
            raise ValueError("call fit() before predict()")
        if self._model is not None:
            values = np.asarray(self._model.forecast(horizon), dtype=float)
        else:
            values = np.full(horizon, float(self._series.iloc[-1]), dtype=float)
        upper = max(float(self._series.max()) * 2.0, 1.0)
        values = np.clip(values, 0.0, upper)
        return pd.Series(values, index=_future_index(self._series, horizon))


class _LSTMNetwork(nn.Module):
    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden_size, num_layers=1, batch_first=True)
        self.linear = nn.Linear(hidden_size, 1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.lstm(inputs)
        return self.linear(outputs[:, -1, :]).squeeze(-1)


class LSTMForecastModel:
    """Small PyTorch LSTM trained on sliding windows of the target series."""

    def __init__(
        self,
        lookback: int = DEFAULT_LSTM_LOOKBACK,
        hidden_size: int = DEFAULT_LSTM_HIDDEN,
        epochs: int = DEFAULT_LSTM_EPOCHS,
        learning_rate: float = 0.01,
        batch_size: int = 32,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self.lookback = lookback
        self.hidden_size = hidden_size
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.seed = seed
        self._series: pd.Series | None = None
        self._model: _LSTMNetwork | None = None
        self._minimum = 0.0
        self._span = 1.0
        self._scaled: np.ndarray | None = None

    def fit(self, train: pd.Series) -> "LSTMForecastModel":
        cleaned = _clean_series(train).dropna().sort_index()
        self._series = cleaned
        self._model = None
        values = cleaned.to_numpy(dtype=float)
        if len(values) <= self.lookback + 1:
            return self
        values = values[-min(len(values), 1095) :]
        transformed = np.log1p(np.clip(values, 0.0, None))
        self._minimum = float(np.min(transformed))
        maximum = float(np.max(transformed))
        self._span = maximum - self._minimum
        if self._span <= 1e-9:
            return self
        scaled = (transformed - self._minimum) / self._span
        self._scaled = scaled
        windows = np.lib.stride_tricks.sliding_window_view(scaled, self.lookback + 1)
        features = windows[:, :-1]
        targets = windows[:, -1]
        features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(-1)
        targets_tensor = torch.tensor(targets, dtype=torch.float32)

        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        torch.set_num_threads(1)
        model = _LSTMNetwork(self.hidden_size)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)
        loss_function = nn.MSELoss()
        model.train()
        for _ in range(max(1, self.epochs)):
            permutation = torch.randperm(len(features_tensor))
            for start in range(0, len(features_tensor), self.batch_size):
                indices = permutation[start : start + self.batch_size]
                optimizer.zero_grad()
                predictions = model(features_tensor[indices])
                loss = loss_function(predictions, targets_tensor[indices])
                loss.backward()
                optimizer.step()
        model.eval()
        self._model = model
        return self

    def predict(self, horizon: int) -> pd.Series:
        if self._series is None:
            raise ValueError("call fit() before predict()")
        if self._model is None or self._scaled is None:
            return naive_forecast(self._series, horizon)
        window = self._scaled[-self.lookback :].reshape(1, self.lookback, 1)
        predictions: list[float] = []
        with torch.no_grad():
            for _ in range(horizon):
                inputs = torch.tensor(window, dtype=torch.float32)
                value = float(self._model(inputs).item())
                value = float(np.clip(value, 0.0, 1.0))
                predictions.append(value)
                window = np.concatenate(
                    [window[:, 1:, :], np.array([[[value]]], dtype=float)],
                    axis=1,
                )
        transformed = np.asarray(predictions, dtype=float) * self._span + self._minimum
        values = np.expm1(transformed)
        upper = max(float(self._series.max()) * 2.0, 1.0)
        values = np.clip(values, 0.0, upper)
        return pd.Series(values, index=_future_index(self._series, horizon))


def future_forecast(
    models: Mapping[str, object],
    series: pd.Series,
    horizon: int,
) -> dict[str, pd.Series]:
    """Fit each model on the full series and forecast beyond its last date."""
    cleaned = _clean_series(series).dropna().sort_index()
    if cleaned.empty:
        raise ValueError("cannot forecast an empty series")
    forecasts: dict[str, pd.Series] = {}
    for name, model in models.items():
        if hasattr(model, "fit") and hasattr(model, "predict"):
            fitted = model.fit(cleaned)
            forecast = fitted.predict(horizon)
        elif callable(model):
            forecast = model(cleaned, horizon)
        else:
            raise TypeError(f"unsupported model object for {name!r}")
        forecasts[name] = pd.Series(forecast).astype(float)
    return forecasts


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
