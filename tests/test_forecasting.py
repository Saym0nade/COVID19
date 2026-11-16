from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting import (
    HoltWintersForecastModel,
    LSTMForecastModel,
    evaluate_mae,
    future_forecast,
    make_model,
    naive_forecast,
    time_based_split,
    top_countries_by_latest_total,
)


def daily_series(days: int = 120) -> pd.Series:
    index = pd.date_range("2023-01-01", periods=days, freq="D")
    values = 100 + 20 * np.sin(np.arange(days) / 7) + np.arange(days) * 0.1
    return pd.Series(values, index=index, name="cases")


def test_cutoff_split_has_no_leakage():
    train, test = time_based_split(daily_series(365), cutoff_date="2023-06-30")
    assert train.index.max() <= pd.Timestamp("2023-06-30")
    assert test.index.min() == pd.Timestamp("2023-07-01")
    assert train.index.intersection(test.index).empty


def test_naive_forecast_starts_after_last_observation():
    series = daily_series(30)
    forecast = naive_forecast(series, horizon=5)
    assert len(forecast) == 5
    assert forecast.index.min() == series.index.max() + pd.Timedelta(days=1)
    assert np.allclose(forecast.to_numpy(), series.iloc[-1])


def test_future_forecast_with_callable_model():
    series = daily_series(30)
    forecasts = future_forecast({"naive": make_model(naive_forecast)}, series, 4)
    forecast = forecasts["naive"]
    assert len(forecast) == 4
    assert forecast.index.min() == series.index.max() + pd.Timedelta(days=1)


def test_evaluate_mae_ignores_missing_pairs():
    actual = pd.Series([1.0, 2.0, np.nan, 4.0])
    predicted = pd.Series([2.0, 2.0, 100.0, 6.0])
    assert evaluate_mae(actual, predicted) == 1.0


def test_holt_winters_returns_requested_horizon():
    series = daily_series(120)
    model = HoltWintersForecastModel(season_length=7).fit(series)
    forecast = model.predict(5)
    assert len(forecast) == 5
    assert forecast.index.min() == series.index.max() + pd.Timedelta(days=1)
    assert (forecast >= 0).all()


def test_lstm_returns_requested_horizon():
    series = daily_series(90)
    model = LSTMForecastModel(
        lookback=7,
        hidden_size=4,
        epochs=1,
        batch_size=16,
        seed=1,
    ).fit(series)
    forecast = model.predict(5)
    assert len(forecast) == 5
    assert forecast.index.min() == series.index.max() + pd.Timedelta(days=1)
    assert (forecast >= 0).all()


def test_top_countries_requires_recent_target_data():
    dates = pd.date_range("2023-10-01", periods=150, freq="D")
    rows = []
    for iso, base in (("AAA", 100.0), ("BBB", 50.0)):
        for date in dates:
            rows.append(
                {
                    "iso_code": iso,
                    "location": iso,
                    "date": date,
                    "total_cases": base + 1,
                    "new_cases_smoothed": 1.0 if date > pd.Timestamp("2023-12-31") else 0.0,
                }
            )
    frame = pd.DataFrame(rows)
    frame.loc[frame["iso_code"] == "BBB", "new_cases_smoothed"] = 0.0

    top = top_countries_by_latest_total(
        frame,
        top_n=1,
        target_column="new_cases_smoothed",
        min_target_date="2023-12-31",
        min_target_observations=30,
    )

    assert top["iso_code"].tolist() == ["AAA"]
