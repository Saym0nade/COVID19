from __future__ import annotations

import pandas as pd

from .config import DATE_COLUMN, REGION_COLUMN


def add_derived_fields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if DATE_COLUMN in result:
        result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN], errors="coerce")
        result["year"] = result[DATE_COLUMN].dt.year.astype("Int64")
    else:
        result["year"] = pd.NA
    if REGION_COLUMN in result:
        result["region"] = (
            result[REGION_COLUMN]
            .astype("string")
            .replace("", pd.NA)
            .fillna("Unknown")
        )
    else:
        result["region"] = "Unknown"
    vaccination_column = "people_vaccinated_per_hundred"
    if vaccination_column in result:
        values = pd.to_numeric(result[vaccination_column], errors="coerce")
        result["category"] = pd.cut(
            values,
            bins=[float("-inf"), 0, 40, 70, float("inf")],
            labels=["None", "Low", "Medium", "High"],
            include_lowest=True,
        )
        result["category"] = result["category"].astype("string").fillna("Unknown")
    else:
        result["category"] = "Unknown"
    return result


def descriptive_stats(frame: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")


def missing_report(frame: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")


def detect_outliers_iqr(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")


def correlation_matrix(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    method: str = "pearson",
) -> pd.DataFrame:
    raise NotImplementedError("Phase 1: participant B")
