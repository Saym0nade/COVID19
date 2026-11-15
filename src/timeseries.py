from __future__ import annotations

import pandas as pd


def resample_series(
    frame: pd.DataFrame,
    date_column: str = "date",
    value_column: str = "new_cases",
    frequency: str = "W",
) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")


def rolling_average(
    frame: pd.DataFrame,
    value_column: str = "new_cases",
    window: int = 7,
) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")


def seasonal_decompose(
    frame: pd.DataFrame,
    value_column: str = "new_cases",
    period: int = 7,
) -> object:
    raise NotImplementedError("Phase 1: participant B")


def detect_waves(
    frame: pd.DataFrame,
    value_column: str = "new_cases_smoothed",
    threshold: float = 0.0,
) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")
