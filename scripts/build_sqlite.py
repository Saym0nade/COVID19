from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, MERGED_DATA_PATH, SCHEMA_PATH
from src.db import get_connection, init_db, load_dataframe

METRIC_COLUMNS = [
    "new_cases",
    "total_cases",
    "new_deaths",
    "total_deaths",
    "new_cases_smoothed",
    "new_deaths_smoothed",
]
VACCINATION_COLUMNS = [
    "people_vaccinated",
    "people_fully_vaccinated",
    "total_boosters",
    "people_vaccinated_per_hundred",
    "people_fully_vaccinated_per_hundred",
]
EXCESS_COLUMNS = ["excess_mortality", "excess_mortality_cumulative"]


def _last_valid(values: pd.Series):
    non_null = values.dropna()
    return non_null.iloc[-1] if len(non_null) else None


def _prepare_keys(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    available = [column for column in columns if column in frame.columns]
    subset = frame[available].copy()
    if "iso_code" in subset.columns:
        subset["iso_code"] = subset["iso_code"].astype(str).str.strip()
        subset = subset[subset["iso_code"].notna() & (subset["iso_code"] != "")]
        subset = subset[subset["iso_code"] != "nan"]
    if "date" in subset.columns:
        subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
        subset = subset[subset["date"].notna()]
        subset["date"] = subset["date"].dt.strftime("%Y-%m-%d")
    return subset


def _load_merged() -> pd.DataFrame:
    if MERGED_DATA_PATH.exists():
        return pd.read_parquet(MERGED_DATA_PATH)
    print("Merged parquet missing; building it first ...")
    from src.data_pipeline import (
        clean_data,
        load_merged_data,
        optimize_dtypes,
        save_merged_parquet,
    )

    frame = load_merged_data()
    frame = optimize_dtypes(clean_data(frame))
    save_merged_parquet(frame, MERGED_DATA_PATH)
    return frame


def build_countries(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "iso_code",
        "location",
        "continent",
        "population",
        "gdp_per_capita",
        "human_development_index",
    ]
    available = [column for column in columns if column in frame.columns]
    source = frame[available].copy()
    source["iso_code"] = source["iso_code"].astype(str).str.strip()
    source = source[source["iso_code"].notna() & (source["iso_code"] != "")]
    source = source[source["iso_code"] != "nan"]
    if "date" in frame.columns:
        source["_sort_date"] = pd.to_datetime(frame.loc[source.index, "date"], errors="coerce")
        source = source.sort_values("_sort_date")
    agg = {column: _last_valid for column in available if column != "iso_code"}
    countries = source.groupby("iso_code", sort=False).agg(agg).reset_index()
    if "location" in countries.columns:
        countries["location"] = countries["location"].fillna(countries["iso_code"])
    else:
        countries["location"] = countries["iso_code"]
    return countries


def build_covid_metrics(frame: pd.DataFrame, valid_codes: set[str]) -> pd.DataFrame:
    columns = ["iso_code", "date", *METRIC_COLUMNS]
    metrics = _prepare_keys(frame, columns)
    metrics = metrics.dropna(subset=METRIC_COLUMNS, how="all")
    metrics = metrics.drop_duplicates(subset=["iso_code", "date"], keep="last")
    metrics = metrics[metrics["iso_code"].isin(valid_codes)]
    return metrics


def build_vaccinations(frame: pd.DataFrame, valid_codes: set[str]) -> pd.DataFrame:
    columns = ["iso_code", "date", *VACCINATION_COLUMNS]
    vaccinations = _prepare_keys(frame, columns)
    vaccinations = vaccinations.dropna(subset=VACCINATION_COLUMNS, how="all")
    vaccinations = vaccinations.drop_duplicates(subset=["iso_code", "date"], keep="last")
    vaccinations = vaccinations[vaccinations["iso_code"].isin(valid_codes)]
    return vaccinations


def build_excess_mortality(frame: pd.DataFrame, valid_codes: set[str]) -> pd.DataFrame:
    columns = ["iso_code", "date", *EXCESS_COLUMNS]
    excess = _prepare_keys(frame, columns)
    excess = excess.dropna(subset=EXCESS_COLUMNS, how="all")
    excess = excess.drop_duplicates(subset=["iso_code", "date"], keep="last")
    excess = excess[excess["iso_code"].isin(valid_codes)]
    return excess


def main() -> None:
    try:
        frame = _load_merged()
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Failed to read/build merged dataset: {exc}")
        raise SystemExit(1) from exc

    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
        connection = get_connection(DB_PATH)
        init_db(connection, SCHEMA_PATH)
    except (OSError, sqlite3.Error) as exc:
        print(f"Failed to initialise database: {exc}")
        raise SystemExit(1) from exc

    try:
        countries = build_countries(frame)
        valid_codes = set(countries["iso_code"].tolist())
        covid_metrics = build_covid_metrics(frame, valid_codes)
        vaccinations = build_vaccinations(frame, valid_codes)
        excess_mortality = build_excess_mortality(frame, valid_codes)

        load_dataframe(countries, "countries", connection, if_exists="append")
        load_dataframe(covid_metrics, "covid_metrics", connection, if_exists="append")
        load_dataframe(vaccinations, "vaccinations", connection, if_exists="append")
        load_dataframe(excess_mortality, "excess_mortality", connection, if_exists="append")
        connection.commit()
    except (KeyError, ValueError, sqlite3.Error) as exc:
        connection.close()
        print(f"Failed to populate database: {exc}")
        raise SystemExit(1) from exc

    try:
        for table in ("countries", "covid_metrics", "vaccinations", "excess_mortality", "waves"):
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count} rows")
        print(f"database path: {DB_PATH}")
    except sqlite3.Error as exc:
        print(f"Failed to read row counts: {exc}")
        raise SystemExit(1) from exc
    finally:
        connection.close()


if __name__ == "__main__":
    main()
