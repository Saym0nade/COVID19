from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import (
    CATALOG_COMPACT_PATH,
    CATALOG_RENAME,
    CORE_COLUMNS,
    COUNTRY_CODE_COLUMN,
    DATE_COLUMN,
    LOCATION_COLUMN,
    MERGED_DATA_PATH,
    NUMERIC_COLUMNS,
    PROCESSED_DATA_PATH,
    RAW_DATA_PATH,
)


def load_raw(
    path: Path = RAW_DATA_PATH,
    usecols: list[str] | None = None,
    chunksize: int | None = None,
) -> pd.DataFrame | pd.io.parsers.TextFileReader:
    if not path.exists():
        raise FileNotFoundError(f"Raw data not found: {path}")
    return pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False)


def load_catalog(
    path: Path = CATALOG_COMPACT_PATH,
    usecols: list[str] | None = None,
    chunksize: int | None = None,
) -> pd.DataFrame | pd.io.parsers.TextFileReader:
    if not path.exists():
        raise FileNotFoundError(f"Catalog data not found: {path}")
    return pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False)


def normalize_catalog_compact(frame: pd.DataFrame) -> pd.DataFrame:
    rename = {source: target for source, target in CATALOG_RENAME.items() if source in frame.columns}
    result = frame.rename(columns=rename).copy()
    if DATE_COLUMN in result:
        result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def clean_data(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if DATE_COLUMN in result:
        result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    keys = [column for column in (COUNTRY_CODE_COLUMN, DATE_COLUMN) if column in result]
    if keys:
        result = result.drop_duplicates(subset=keys, keep="last")
    return result


def _deduplicate_keeping_missing_codes(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    valid = frame[frame[COUNTRY_CODE_COLUMN].notna()].drop_duplicates(subset=keys, keep="last")
    missing = frame[frame[COUNTRY_CODE_COLUMN].isna()]
    if DATE_COLUMN in missing.columns and LOCATION_COLUMN in missing.columns:
        missing = missing.drop_duplicates(subset=[LOCATION_COLUMN, DATE_COLUMN], keep="last")
    return pd.concat([valid, missing])


def _legacy_location_code_map(legacy: pd.DataFrame) -> dict:
    if LOCATION_COLUMN not in legacy.columns or COUNTRY_CODE_COLUMN not in legacy.columns:
        return {}
    mapping = legacy.dropna(subset=[LOCATION_COLUMN, COUNTRY_CODE_COLUMN]).drop_duplicates(
        LOCATION_COLUMN
    )
    return mapping.set_index(LOCATION_COLUMN)[COUNTRY_CODE_COLUMN].to_dict()


def merge_new_and_legacy(new_frame: pd.DataFrame, legacy_frame: pd.DataFrame) -> pd.DataFrame:
    catalog = normalize_catalog_compact(new_frame)
    legacy = legacy_frame.copy()
    if DATE_COLUMN in legacy:
        legacy[DATE_COLUMN] = pd.to_datetime(legacy[DATE_COLUMN], errors="coerce")
    keys = [COUNTRY_CODE_COLUMN, DATE_COLUMN]
    missing_catalog = [key for key in keys if key not in catalog.columns]
    missing_legacy = [key for key in keys if key not in legacy.columns]
    if missing_catalog or missing_legacy:
        raise ValueError(f"Missing merge keys: catalog={missing_catalog}, legacy={missing_legacy}")
    location_map = _legacy_location_code_map(legacy)
    if LOCATION_COLUMN in catalog.columns:
        catalog[COUNTRY_CODE_COLUMN] = catalog[COUNTRY_CODE_COLUMN].fillna(
            catalog[LOCATION_COLUMN].map(location_map)
        )
    catalog = _deduplicate_keeping_missing_codes(catalog, keys)
    legacy = _deduplicate_keeping_missing_codes(legacy, keys)
    overlap = sorted((set(catalog.columns) & set(legacy.columns)) - set(keys))
    merged = catalog.merge(
        legacy,
        on=keys,
        how="outer",
        suffixes=("__catalog", "__legacy"),
        indicator=True,
    )
    combined = {}
    drop_columns = []
    for column in overlap:
        catalog_column = f"{column}__catalog"
        legacy_column = f"{column}__legacy"
        if catalog_column in merged.columns and legacy_column in merged.columns:
            combined[column] = merged[catalog_column].combine_first(merged[legacy_column])
            drop_columns.extend([catalog_column, legacy_column])
    drop_columns = [column for column in drop_columns if column in merged.columns]
    if drop_columns:
        merged = merged.drop(columns=drop_columns)
    if combined:
        combined_frame = pd.DataFrame(combined, index=merged.index)
        merged = pd.concat([merged, combined_frame], axis=1)
    if "_merge" in merged.columns:
        merged = merged.drop(columns=["_merge"])
    return merged


def load_merged_data(
    legacy_path: Path = RAW_DATA_PATH,
    catalog_path: Path = CATALOG_COMPACT_PATH,
) -> pd.DataFrame:
    catalog = load_catalog(catalog_path)
    legacy = load_raw(legacy_path)
    return merge_new_and_legacy(catalog, legacy)


def optimize_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("iso_code", "continent", "location"):
        if column in result:
            result[column] = result[column].astype("category")
    for column in result.select_dtypes(include="float64").columns:
        result[column] = pd.to_numeric(result[column], downcast="float")
    for column in result.select_dtypes(include="int64").columns:
        result[column] = pd.to_numeric(result[column], downcast="integer")
    return result


def save_parquet(frame: pd.DataFrame, path: Path = PROCESSED_DATA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def save_merged_parquet(frame: pd.DataFrame, path: Path = MERGED_DATA_PATH) -> Path:
    return save_parquet(frame, path)


def build_data_profile(
    frame: pd.DataFrame,
    key_columns: list[str] | None = None,
) -> dict:
    """Build a JSON-serialisable profile of a merged dataset."""
    if key_columns is None:
        key_columns = [column for column in CORE_COLUMNS if column in frame.columns]
    date_min = date_max = None
    if DATE_COLUMN in frame.columns:
        dates = pd.to_datetime(frame[DATE_COLUMN], errors="coerce")
        if dates.notna().any():
            date_min = dates.min().date().isoformat()
            date_max = dates.max().date().isoformat()
    missing = {
        column: int(frame[column].isna().sum())
        for column in key_columns
        if column in frame.columns
    }
    return {
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "date_min": date_min,
        "date_max": date_max,
        "memory_mb": round(float(frame.memory_usage(deep=True).sum()) / 1_048_576, 2),
        "missing": missing,
    }


def save_data_profile(profile: dict, path: Path) -> Path:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def chunked_summary(path: Path = RAW_DATA_PATH, chunk_size: int = 100_000) -> dict:
    chunks = load_raw(path, chunksize=chunk_size)
    sizes = [len(chunk) for chunk in chunks]
    return {
        "chunks": len(sizes),
        "rows": sum(sizes),
        "chunk_size": chunk_size,
        "max_chunk_rows": max(sizes) if sizes else 0,
    }
