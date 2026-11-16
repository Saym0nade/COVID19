from __future__ import annotations

import pandas as pd


def resample_series(
    frame: pd.DataFrame,
    date_column: str = "date",
    value_column: str = "new_cases",
    frequency: str = "W",
    group_columns: list[str] | None = None,
    agg: str = "sum",
) -> pd.DataFrame:
    """Resample ``value_column`` at ``frequency`` with optional grouping.

    ``agg="sum"`` is appropriate for flow metrics such as ``new_cases``;
    ``agg="last"`` is appropriate for already-smoothed/stock values. The
    returned frame contains the group columns (when provided), the resampled
    date column, the value column and a ``frequency`` label.
    """
    if date_column not in frame.columns:
        raise KeyError(f"Missing date column: {date_column}")
    if value_column not in frame.columns:
        raise KeyError(f"Missing value column: {value_column}")

    work = frame.copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work = work.dropna(subset=[date_column])

    groups = [column for column in (group_columns or []) if column in work.columns]
    grouper = groups + [pd.Grouper(key=date_column, freq=frequency)]
    grouped = work.groupby(grouper, observed=True, dropna=False)[value_column]

    if agg == "sum":
        resampled = grouped.sum(min_count=1)
    elif agg in {"mean", "max", "min", "median", "last", "first"}:
        resampled = grouped.agg(agg)
    else:
        raise ValueError(f"Unsupported aggregation: {agg}")

    result = resampled.reset_index()
    result = result.dropna(subset=[date_column])
    result["frequency"] = frequency
    return result.sort_values(groups + [date_column]).reset_index(drop=True)


def rolling_average(
    frame: pd.DataFrame,
    value_column: str = "new_cases",
    window: int = 7,
    group_columns: list[str] | None = None,
    date_column: str = "date",
    min_periods: int = 1,
    column_name: str | None = None,
) -> pd.DataFrame:
    """Add a rolling mean column for ``value_column``.

    Grouping (for example by ``iso_code``/``location``) prevents rolling
    values from leaking across countries. The new column defaults to
    ``rolling_<window>``.
    """
    if value_column not in frame.columns:
        raise KeyError(f"Missing value column: {value_column}")

    result = frame.copy()
    result[value_column] = pd.to_numeric(result[value_column], errors="coerce")
    if date_column in result.columns:
        result[date_column] = pd.to_datetime(result[date_column], errors="coerce")

    output_column = column_name or f"rolling_{window}"
    groups = [column for column in (group_columns or []) if column in result.columns]

    sort_columns = groups + ([date_column] if date_column in result.columns else [])
    if sort_columns:
        result = result.sort_values(sort_columns, kind="stable").reset_index(drop=True)

    if groups:
        grouped = result.groupby(groups, observed=True, dropna=False)[value_column]
        result[output_column] = grouped.transform(
            lambda series: series.rolling(window, min_periods=min_periods).mean()
        )
    else:
        result[output_column] = result[value_column].rolling(
            window, min_periods=min_periods
        ).mean()
    return result


def seasonal_decompose(
    frame: pd.DataFrame,
    value_column: str = "new_cases",
    period: int = 7,
) -> object:
    raise NotImplementedError("Phase 2: seasonal decomposition")


def detect_waves(
    frame: pd.DataFrame,
    value_column: str = "new_cases_smoothed",
    threshold: float = 0.0,
) -> pd.DataFrame:
    raise NotImplementedError("Phase 2: wave detection")
