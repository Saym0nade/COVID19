from __future__ import annotations

import pandas as pd

from src.data_pipeline import clean_data, merge_new_and_legacy


def test_merge_prefers_catalog_and_keeps_legacy_only_columns():
    catalog = pd.DataFrame(
        {
            "code": ["A", "B"],
            "country": ["Alpha", "Beta"],
            "date": ["2020-01-01", "2020-01-02"],
            "new_cases": [10, None],
            "continent": ["X", None],
        }
    )
    legacy = pd.DataFrame(
        {
            "iso_code": ["A", "B"],
            "location": ["Alpha", "Beta"],
            "date": ["2020-01-01", "2020-01-02"],
            "new_cases": [5, 7],
            "continent": ["Old", "Old"],
            "aged_65_older": [3.0, 4.0],
        }
    )

    merged = merge_new_and_legacy(catalog, legacy).sort_values("iso_code")

    assert merged["new_cases"].tolist() == [10.0, 7.0]
    assert merged["continent"].tolist() == ["X", "Old"]
    assert merged["aged_65_older"].tolist() == [3.0, 4.0]
    assert "location" in merged.columns


def test_merge_preserves_rows_with_missing_catalog_code():
    catalog = pd.DataFrame(
        {
            "code": [None],
            "country": ["Asia excl. China"],
            "date": ["2020-01-01"],
            "new_cases": [1],
        }
    )
    legacy = pd.DataFrame(
        {
            "iso_code": ["OWID_ASI"],
            "location": ["Asia excl. China"],
            "date": ["2020-01-01"],
            "new_cases": [2],
        }
    )

    merged = merge_new_and_legacy(catalog, legacy)

    assert len(merged) == 1
    assert merged.iloc[0]["iso_code"] == "OWID_ASI"
    assert merged.iloc[0]["new_cases"] == 1


def test_clean_data_deduplicates_and_converts_types():
    frame = pd.DataFrame(
        {
            "iso_code": ["A", "A"],
            "date": ["2020-01-01", "2020-01-01"],
            "new_cases": ["1", "2"],
        }
    )

    cleaned = clean_data(frame)

    assert len(cleaned) == 1
    assert str(cleaned["date"].dtype).startswith("datetime64")
    assert cleaned.iloc[0]["new_cases"] == 2.0
