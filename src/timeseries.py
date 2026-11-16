from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks


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


@dataclass
class SeasonalDecompositionResult:
    """Container returned by :func:`seasonal_decompose`.

    The component series are indexed by date. ``to_dict`` and ``summary``
    return JSON-serializable structures, so the result can either be used as
    an object (``.observed``, ``.trend``, ...) or written to the runner's
    summary directly.
    """

    value_column: str
    period: int
    model: str
    frequency: str
    observed: pd.Series
    trend: pd.Series
    seasonal: pd.Series
    resid: pd.Series

    def to_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(
            {
                "date": self.observed.index,
                "observed": self.observed.to_numpy(),
                "trend": self.trend.to_numpy(),
                "seasonal": self.seasonal.to_numpy(),
                "resid": self.resid.to_numpy(),
            }
        )
        return frame

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_column": self.value_column,
            "period": self.period,
            "model": self.model,
            "frequency": self.frequency,
            "observations": int(self.observed.shape[0]),
            **self.summary(),
            "components": [
                {
                    "date": date.isoformat(),
                    "observed": _finite_or_none(row.observed),
                    "trend": _finite_or_none(row.trend),
                    "seasonal": _finite_or_none(row.seasonal),
                    "resid": _finite_or_none(row.resid),
                }
                for date, row in self.to_frame()
                .set_index("date")
                .iterrows()
            ],
        }

    def summary(self) -> dict[str, float | None]:
        """Return variance-based strength diagnostics (0-1, higher = stronger)."""
        observed_var = float(np.nanvar(self.observed.to_numpy()))
        resid_var = float(np.nanvar(self.resid.to_numpy()))
        detrended = self.observed.to_numpy() - np.nan_to_num(
            self.trend.to_numpy(), nan=np.nanmean(self.trend.to_numpy())
        )
        detrended_var = float(np.nanvar(detrended))
        return {
            "trend_strength": _bounded_strength(1.0 - resid_var / observed_var)
            if observed_var > 0
            else None,
            "seasonal_strength": _bounded_strength(1.0 - resid_var / detrended_var)
            if detrended_var > 0
            else None,
        }


def _finite_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _bounded_strength(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def seasonal_decompose(
    frame: pd.DataFrame,
    value_column: str = "new_cases",
    period: int = 7,
    date_column: str = "date",
    agg: str = "sum",
    model: str = "additive",
) -> SeasonalDecompositionResult:
    """Decompose a daily series into trend/seasonal/residual components.

    Rows are aggregated to one observation per day (``agg="sum"`` for flows),
    the daily calendar is reindexed, and internal gaps are linearly
    interpolated because ``statsmodels`` requires a complete series. The
    ``period`` defaults to 7 (weekly seasonality in daily data). Returns a
    :class:`SeasonalDecompositionResult` exposing the component series and
    JSON-serializable ``to_dict``/``summary`` helpers.
    """
    from statsmodels.tsa.seasonal import seasonal_decompose as _decompose

    if value_column not in frame.columns:
        raise KeyError(f"Missing value column: {value_column}")
    if date_column not in frame.columns:
        raise KeyError(f"Missing date column: {date_column}")
    if period < 2:
        raise ValueError("period must be >= 2")

    work = frame[[date_column, value_column]].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work = work.dropna(subset=[date_column, value_column])
    if work.empty:
        raise ValueError("No non-null observations available for decomposition")

    daily = work.groupby(date_column, observed=True)[value_column].agg(agg)
    daily = daily.sort_index()
    daily = daily.asfreq("D")
    daily = daily.interpolate(method="time", limit_direction="both")

    if len(daily) < 2 * period:
        raise ValueError(
            f"Need at least {2 * period} daily observations, got {len(daily)}"
        )

    decomposition = _decompose(daily, model=model, period=period, extrapolate_trend="period")
    return SeasonalDecompositionResult(
        value_column=value_column,
        period=period,
        model=model,
        frequency="D",
        observed=decomposition.observed,
        trend=decomposition.trend,
        seasonal=decomposition.seasonal,
        resid=decomposition.resid,
    )


WAVE_COLUMNS = [
    "iso_code",
    "location",
    "wave_number",
    "start_date",
    "end_date",
    "peak_date",
    "peak_value",
    "duration_days",
    "method",
]


def detect_waves(
    frame: pd.DataFrame,
    value_column: str = "new_cases_smoothed",
    *,
    date_column: str = "date",
    group_columns: tuple[str, ...] = ("iso_code", "location"),
    rolling_window: int = 7,
    distance_days: int = 30,
    prominence_ratio: float = 0.05,
    onset_ratio: float = 0.10,
    min_peak_value: float = 0.0,
    include_aggregates: bool = False,
) -> pd.DataFrame:
    """Detect per-country waves with a smoothed-series + peak-finding hybrid.

    Method
    ------
    1. Keep one observation per country/date and apply a trailing
       ``rolling_window``-day mean (default 7) to reduce day-of-week noise and
       reporting artefacts.
    2. Run ``scipy.signal.find_peaks`` on that smoothed series with:

       - ``distance = distance_days`` (minimum 30 days between wave peaks),
       - ``height = max(min_peak_value, prominence_ratio * series_max)``,
       - ``prominence = prominence_ratio * series_max`` (default 5% of the
         country's largest smoothed value).

    3. For every detected peak define the wave interval by walking outward
       until the smoothed value falls to ``onset_ratio`` (default 10%) of that
       peak's value. Intervals are then clipped so consecutive waves do not
       overlap; the first/last wave is clipped to the observed date range.

    Parameters are deliberately conservative (30-day spacing, 5% prominence)
    so that small reporting blips are not labelled as separate waves.

    Returns
    -------
    DataFrame with exactly ``WAVE_COLUMNS``. Aggregates (``OWID_*``) are
    excluded by default to avoid double counting global/regional series.
    """
    required = [column for column in (date_column, value_column) if column in frame.columns]
    if date_column not in frame.columns:
        raise KeyError(f"Missing date column: {date_column}")
    if value_column not in frame.columns:
        raise KeyError(f"Missing value column: {value_column}")

    work = frame.copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work = work.dropna(subset=[date_column, value_column])
    if not include_aggregates and "iso_code" in work.columns:
        iso = work["iso_code"].astype("string").str.strip()
        work = work[
            iso.notna()
            & (iso != "")
            & ~iso.str.startswith("OWID_", na=False)
        ]
    if work.empty:
        return pd.DataFrame(columns=WAVE_COLUMNS)

    groups = [column for column in group_columns if column in work.columns]
    method = (
        f"rolling_{rolling_window}+find_peaks("
        f"prominence_ratio={prominence_ratio:g},"
        f"distance={distance_days}d,onset_ratio={onset_ratio:g})"
    )

    records: list[dict[str, Any]] = []
    group_iterator = (
        work.groupby(groups, observed=True, dropna=False, sort=True)
        if groups
        else [((None,), work)]
    )
    for key, group in group_iterator:
        if not isinstance(key, tuple):
            key = (key,)
        metadata = dict(zip(groups, key)) if groups else {}

        series = (
            group.groupby(date_column, observed=True)[value_column]
            .mean()
            .sort_index()
        )
        series = series.asfreq("D")
        series = series.interpolate(method="time", limit_direction="both")
        if series.dropna().empty:
            continue
        series = series.dropna()
        if series.shape[0] < rolling_window + 2:
            continue

        smoothed = series.rolling(rolling_window, min_periods=1).mean()
        values = smoothed.to_numpy(dtype=float)
        peak_max = float(np.nanmax(values))
        if not np.isfinite(peak_max) or peak_max <= 0:
            continue

        height = max(min_peak_value, prominence_ratio * peak_max)
        prominence = prominence_ratio * peak_max
        peak_indices, _ = find_peaks(
            values,
            distance=max(1, int(distance_days)),
            height=height,
            prominence=prominence,
        )
        if peak_indices.size == 0:
            continue

        previous_end: pd.Timestamp | None = None
        wave_number = 0
        for peak_index in peak_indices:
            peak_value = float(values[peak_index])
            threshold = onset_ratio * peak_value

            start_index = peak_index
            while start_index > 0 and values[start_index - 1] > threshold:
                start_index -= 1
            end_index = peak_index
            last_index = values.shape[0] - 1
            while end_index < last_index and values[end_index + 1] > threshold:
                end_index += 1

            start_date = smoothed.index[start_index]
            end_date = smoothed.index[end_index]
            if previous_end is not None and start_date <= previous_end:
                while (
                    start_index < values.shape[0]
                    and smoothed.index[start_index] <= previous_end
                ):
                    start_index += 1
                if start_index >= values.shape[0] or start_index > peak_index:
                    continue
                start_date = smoothed.index[start_index]
            if end_date < smoothed.index[peak_index]:
                end_date = smoothed.index[peak_index]
            if end_date < start_date:
                continue

            wave_number += 1
            record = {
                "iso_code": metadata.get("iso_code"),
                "location": metadata.get("location"),
                "wave_number": wave_number,
                "start_date": start_date,
                "end_date": end_date,
                "peak_date": smoothed.index[peak_index],
                "peak_value": peak_value,
                "duration_days": int((end_date - start_date).days) + 1,
                "method": method,
            }
            records.append(record)
            previous_end = end_date

    result = pd.DataFrame.from_records(records)
    if result.empty:
        return pd.DataFrame(columns=WAVE_COLUMNS)
    return result[WAVE_COLUMNS]
