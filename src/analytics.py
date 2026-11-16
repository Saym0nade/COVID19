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
    """Return descriptive statistics for every numeric column.

    Columns: column, count, missing, mean, std, min, q25, median, q75, max.
    """
    result_columns = [
        "column",
        "count",
        "missing",
        "mean",
        "std",
        "min",
        "q25",
        "median",
        "q75",
        "max",
    ]
    numeric = frame.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame(columns=result_columns)

    stats = numeric.describe().T
    stats = stats.rename(columns={"25%": "q25", "50%": "median", "75%": "q75"})
    stats.index.name = "column"
    stats = stats.reset_index()
    stats["missing"] = numeric.isna().sum().reindex(stats["column"]).to_numpy()
    ordered = [column for column in result_columns if column in stats.columns]
    return stats[ordered].reset_index(drop=True)


def missing_report(frame: pd.DataFrame) -> pd.DataFrame:
    """Report missing values per column with counts and percentages."""
    total_rows = len(frame)
    report = pd.DataFrame(
        {
            "column": frame.columns.astype(str),
            "dtype": [str(dtype) for dtype in frame.dtypes],
            "missing_count": frame.isna().sum().to_numpy(dtype="int64"),
        }
    )
    report["present_count"] = total_rows - report["missing_count"]
    if total_rows:
        report["missing_percent"] = report["missing_count"] / total_rows * 100.0
    else:
        report["missing_percent"] = 0.0
    return report.reset_index(drop=True)


def iqr_bounds(frame: pd.DataFrame, column: str) -> dict | None:
    """Compute IQR bounds and outlier counts for a single column."""
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce")
    clean = values.dropna()
    if clean.empty:
        return None
    q1 = float(clean.quantile(0.25))
    q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    mask = values.notna() & ((values < lower_bound) | (values > upper_bound))
    return {
        "column": column,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "outlier_count": int(mask.sum()),
        "non_null_count": int(clean.shape[0]),
    }


def detect_outliers_iqr(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return rows outside the 1.5 x IQR bounds for ``column``.

    Output columns: iso_code, location, date, column, value, lower_bound,
    upper_bound.
    """
    result_columns = [
        "iso_code",
        "location",
        "date",
        "column",
        "value",
        "lower_bound",
        "upper_bound",
    ]
    bounds = iqr_bounds(frame, column)
    if bounds is None:
        return pd.DataFrame(columns=result_columns)

    values = pd.to_numeric(frame[column], errors="coerce")
    mask = values.notna() & (
        (values < bounds["lower_bound"]) | (values > bounds["upper_bound"])
    )
    subset = frame.loc[mask]
    result = pd.DataFrame(
        {
            "iso_code": subset["iso_code"] if "iso_code" in subset else pd.NA,
            "location": subset["location"] if "location" in subset else pd.NA,
            "date": subset["date"] if "date" in subset else pd.NA,
            "column": column,
            "value": values.loc[mask].to_numpy(),
            "lower_bound": bounds["lower_bound"],
            "upper_bound": bounds["upper_bound"],
        },
        index=subset.index,
    )
    return result[result_columns]


def outlier_summary(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Aggregate IQR bounds and outlier counts for several columns."""
    records = []
    for column in columns:
        bounds = iqr_bounds(frame, column)
        if bounds is not None:
            records.append(bounds)
    return pd.DataFrame(
        records,
        columns=[
            "column",
            "q1",
            "q3",
            "iqr",
            "lower_bound",
            "upper_bound",
            "outlier_count",
            "non_null_count",
        ],
    )


def correlation_matrix(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    method: str = "pearson",
) -> pd.DataFrame:
    """Correlation matrix for numeric columns (or an explicit subset)."""
    if columns is None:
        selected = frame.select_dtypes(include="number")
    else:
        available = [column for column in columns if column in frame.columns]
        selected = frame[available].apply(pd.to_numeric, errors="coerce")
    if selected.empty:
        return pd.DataFrame()
    return selected.corr(method=method)


def vaccination_mortality_summary(
    frame: pd.DataFrame,
    group_column: str = "region",
) -> pd.DataFrame:
    """Vaccination and mortality summary by a grouping column.

    Uses the maximum observed coverage/deaths in each group and counts the
    distinct country codes. Returns an empty DataFrame when inputs are missing.
    """
    if group_column not in frame.columns:
        return pd.DataFrame()
    result = frame.copy()
    if "iso_code" in result.columns:
        iso = result["iso_code"].astype("string")
        result = result[~iso.str.startswith("OWID_", na=False)]

    aggregations = {}
    for column in (
        "people_vaccinated_per_hundred",
        "people_fully_vaccinated_per_hundred",
        "total_boosters_per_hundred",
        "total_deaths_per_million",
        "total_cases_per_million",
    ):
        if column in result.columns:
            aggregations[column] = "max"
    if not aggregations:
        return pd.DataFrame()

    grouped = result.groupby(group_column, observed=True, dropna=False)
    summary = grouped.agg(aggregations)
    if "iso_code" in result.columns:
        summary["country_count"] = grouped["iso_code"].nunique()
    summary.index.name = group_column
    return summary.reset_index().sort_values(group_column, na_position="last")
