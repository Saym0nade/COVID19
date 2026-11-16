from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics import (
    add_derived_fields,
    correlation_matrix,
    detect_outliers_iqr,
    missing_report,
)
from src.timeseries import detect_waves, resample_series, rolling_average


def sample_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=60, freq="D")
    return pd.DataFrame(
        {
            "iso_code": ["AAA"] * 30 + ["BBB"] * 30,
            "location": ["Alpha"] * 30 + ["Beta"] * 30,
            "date": list(dates[:30]) + list(dates[30:]),
            "new_cases": list(np.arange(30, dtype=float))
            + list(np.arange(30, dtype=float) + 100),
            "people_vaccinated_per_hundred": [0] * 10
            + [45] * 10
            + [80] * 10
            + [10] * 30,
        }
    )


def test_add_derived_fields_bins_vaccination():
    frame = add_derived_fields(sample_frame())
    assert {"year", "region", "category"}.issubset(frame.columns)
    assert set(frame["category"].unique()).issubset(
        {"None", "Low", "Medium", "High", "Unknown"}
    )
    assert frame["year"].notna().all()


def test_missing_report_and_correlation():
    frame = sample_frame()
    report = missing_report(frame)
    assert {"column", "missing_count", "missing_percent"}.issubset(report.columns)
    corr = correlation_matrix(frame, columns=["new_cases", "people_vaccinated_per_hundred"])
    assert corr.shape == (2, 2)


def test_detect_outliers_iqr_returns_expected_columns():
    frame = sample_frame()
    frame.loc[0, "new_cases"] = 10_000.0
    outliers = detect_outliers_iqr(frame, "new_cases")
    assert not outliers.empty
    assert set(outliers.columns) == {
        "iso_code",
        "location",
        "date",
        "column",
        "value",
        "lower_bound",
        "upper_bound",
    }


def test_resample_series_weekly_sum():
    frame = sample_frame()
    weekly = resample_series(
        frame,
        value_column="new_cases",
        frequency="W",
        group_columns=["iso_code"],
        agg="sum",
    )
    assert "frequency" in weekly.columns
    assert weekly["frequency"].eq("W").all()
    assert weekly["new_cases"].notna().all()


def test_rolling_average_does_not_leak_across_groups():
    frame = sample_frame()
    rolled = rolling_average(
        frame,
        value_column="new_cases",
        window=3,
        group_columns=["iso_code"],
    )
    first_b = rolled[rolled["iso_code"] == "BBB"].iloc[0]
    assert first_b["rolling_3"] == first_b["new_cases"]


def test_detect_waves_returns_contract_columns():
    dates = pd.date_range("2023-01-01", periods=180, freq="D")
    values = 100 + 80 * np.sin(np.arange(180) / 18) ** 2
    frame = pd.DataFrame(
        {
            "iso_code": ["AAA"] * 180,
            "location": ["Alpha"] * 180,
            "date": dates,
            "new_cases_smoothed": values,
        }
    )
    waves = detect_waves(frame, value_column="new_cases_smoothed", distance_days=30)
    assert list(waves.columns) == [
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
    if not waves.empty:
        assert waves["wave_number"].between(1, 10).all()
