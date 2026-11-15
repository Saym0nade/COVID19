from __future__ import annotations

import pandas as pd


def naive_forecast(series: pd.Series, horizon: int) -> pd.Series:
    raise NotImplementedError("Phase 1: participant C")


def seasonal_naive_forecast(series: pd.Series, horizon: int, season_length: int = 7) -> pd.Series:
    raise NotImplementedError("Phase 1: participant C")


def moving_average_forecast(series: pd.Series, horizon: int, window: int = 7) -> pd.Series:
    raise NotImplementedError("Phase 1: participant C")


def linear_regression_forecast(series: pd.Series, horizon: int) -> pd.Series:
    raise NotImplementedError("Phase 1: participant C")


def evaluate_mae(actual: pd.Series, predicted: pd.Series) -> float:
    raise NotImplementedError("Phase 1: participant C")


def benchmark(models: dict, actual: pd.Series) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant C")
