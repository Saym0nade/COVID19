from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CATALOG_DIR = RAW_DIR / "catalog"
SAMPLE_DIR = ROOT / "data" / "sample"
MANIFEST_PATH = ROOT / "data" / "manifest.json"

LEGACY_MAIN_FILE = "owid-covid-data.csv"
LEGACY_SAMPLE_FILE = "owid-covid-sample.csv"
CATALOG_MAIN_FILE = "compact.csv"
CATALOG_SAMPLE_FILE = "owid-catalog-sample.csv"
SAMPLE_STEP = 8
CATALOG_RENAME = {"code": "iso_code", "country": "location"}
CATALOG_DOCS_URL = "https://docs.owid.io/projects/etl/api/covid/#download-data"

LEGACY_SOURCES = {
    "owid-covid-data.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv",
    "vaccinations.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv",
    "vaccinations-by-age-group.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations-by-age-group.csv",
    "vaccinations-by-manufacturer.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations-by-manufacturer.csv",
    "excess_mortality.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/excess_mortality/excess_mortality.csv",
    "covid-testing-all-observations.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/testing/covid-testing-all-observations.csv",
    "covid-hospitalizations.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/hospitalizations/covid-hospitalizations.csv",
    "who-covid-cases-deaths.csv": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/cases_deaths/COVID-19%20Cases%20and%20deaths%20-%20WHO.csv",
}

CATALOG_DATA_URLS = {
    "compact.csv": "https://catalog.ourworldindata.org/garden/covid/latest/compact/compact.csv",
    "cases_deaths.csv": "https://catalog.ourworldindata.org/garden/covid/latest/cases_deaths/cases_deaths.csv",
    "excess_mortality.csv": "https://catalog.ourworldindata.org/garden/excess_mortality/latest/excess_mortality/excess_mortality.csv",
    "excess_mortality_economist.csv": "https://catalog.ourworldindata.org/garden/excess_mortality/latest/excess_mortality_economist/excess_mortality_economist.csv",
    "hospital.csv": "https://catalog.ourworldindata.org/garden/covid/latest/hospital/hospital.csv",
    "vaccinations_global.csv": "https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_global/vaccinations_global.csv",
    "vaccinations_age.csv": "https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_age/vaccinations_age.csv",
    "vaccinations_manufacturer.csv": "https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_manufacturer/vaccinations_manufacturer.csv",
    "vaccinations_us.csv": "https://catalog.ourworldindata.org/garden/covid/latest/vaccinations_us/vaccinations_us.csv",
    "testing.csv": "https://catalog.ourworldindata.org/garden/covid/latest/testing/testing.csv",
    "tracking_r.csv": "https://catalog.ourworldindata.org/garden/covid/latest/tracking_r/tracking_r.csv",
    "google_mobility.csv": "https://catalog.ourworldindata.org/garden/covid/latest/google_mobility/google_mobility.csv",
    "oxcgrt_policy.csv": "https://catalog.ourworldindata.org/garden/covid/latest/oxcgrt_policy/oxcgrt_policy.csv",
    "yougov_composite.csv": "https://catalog.ourworldindata.org/garden/covid/latest/yougov/yougov_composite.csv",
    "covax.csv": "https://catalog.ourworldindata.org/garden/covid/latest/covax/covax.csv",
}

CATALOG_METADATA_URLS = {
    name.replace(".csv", ".meta.json"): url.replace(".csv", ".meta.json")
    for name, url in CATALOG_DATA_URLS.items()
}


def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def file_info(path: Path, source_url: str | None = None, count_data_rows: bool = True) -> dict:
    size = path.stat().st_size
    info = {
        "name": path.name,
        "path": str(path.relative_to(ROOT)),
        "bytes": size,
        "megabytes": round(size / 1024 / 1024, 2),
        "source_url": source_url,
    }
    if count_data_rows:
        info["rows"] = count_rows(path)
    return info


def make_sample(
    source: Path,
    destination: Path,
    step: int,
    rename: dict[str, str] | None = None,
) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    rename = rename or {}
    rows = 0
    locations: set[str] = set()
    dates: list[str] = []
    with source.open("r", encoding="utf-8", newline="") as source_handle:
        reader = csv.reader(source_handle)
        header = next(reader)
        output_header = [rename.get(column, column) for column in header]
        location_index = output_header.index("location") if "location" in output_header else None
        date_index = output_header.index("date") if "date" in output_header else None
        with destination.open("w", encoding="utf-8", newline="") as destination_handle:
            writer = csv.writer(destination_handle)
            writer.writerow(output_header)
            for index, row in enumerate(reader):
                if index % step != 0:
                    continue
                writer.writerow(row)
                rows += 1
                if location_index is not None and location_index < len(row):
                    locations.add(row[location_index])
                if date_index is not None and date_index < len(row):
                    dates.append(row[date_index])
    return {
        "path": str(destination.relative_to(ROOT)),
        "rows": rows,
        "columns": len(output_header),
        "locations": len(locations),
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "step": step,
        "renamed_columns": rename,
    }


def build_manifest(legacy_files: list[dict], catalog_files: list[dict], metadata_files: list[dict]) -> dict:
    legacy_bytes = sum(item["bytes"] for item in legacy_files)
    legacy_rows = sum(item["rows"] for item in legacy_files)
    catalog_bytes = sum(item["bytes"] for item in catalog_files)
    catalog_rows = sum(item["rows"] for item in catalog_files)
    metadata_bytes = sum(item["bytes"] for item in metadata_files)
    data_bytes = legacy_bytes + catalog_bytes
    data_rows = legacy_rows + catalog_rows
    all_bytes = data_bytes + metadata_bytes

    legacy_main = next(item for item in legacy_files if item["name"] == LEGACY_MAIN_FILE)
    catalog_main = next(item for item in catalog_files if item["name"] == CATALOG_MAIN_FILE)
    legacy_sample = make_sample(RAW_DIR / LEGACY_MAIN_FILE, SAMPLE_DIR / LEGACY_SAMPLE_FILE, SAMPLE_STEP)
    catalog_sample = make_sample(
        CATALOG_DIR / CATALOG_MAIN_FILE,
        SAMPLE_DIR / CATALOG_SAMPLE_FILE,
        SAMPLE_STEP,
        rename=CATALOG_RENAME,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Our World in Data COVID-19 dataset",
        "sources": {
            "catalog": {
                "role": "primary",
                "documentation": CATALOG_DOCS_URL,
                "note": "Current ETL catalog exports; use as the primary source.",
            },
            "legacy_github": {
                "role": "fallback",
                "repository": "https://github.com/owid/covid-19-data",
                "note": "Legacy GitHub exports; retained because they may contain fields or observations missing from the catalog.",
            },
        },
        "source_priority": {
            "primary": "catalog",
            "fallback": "legacy_github",
            "merge_rule": "Outer merge on iso_code + date; catalog values win when present, legacy values fill gaps and old-only columns are retained.",
        },
        "legacy_files": legacy_files,
        "catalog_files": catalog_files,
        "catalog_metadata_files": metadata_files,
        "totals": {
            "legacy_files": len(legacy_files),
            "legacy_bytes": legacy_bytes,
            "legacy_megabytes": round(legacy_bytes / 1024 / 1024, 2),
            "legacy_rows": legacy_rows,
            "catalog_files": len(catalog_files),
            "catalog_bytes": catalog_bytes,
            "catalog_megabytes": round(catalog_bytes / 1024 / 1024, 2),
            "catalog_rows": catalog_rows,
            "catalog_metadata_files": len(metadata_files),
            "catalog_metadata_bytes": metadata_bytes,
            "catalog_metadata_megabytes": round(metadata_bytes / 1024 / 1024, 2),
            "data_files": len(legacy_files) + len(catalog_files),
            "data_bytes": data_bytes,
            "data_megabytes": round(data_bytes / 1024 / 1024, 2),
            "data_rows": data_rows,
            "all_files": len(legacy_files) + len(catalog_files) + len(metadata_files),
            "all_bytes": all_bytes,
            "all_megabytes": round(all_bytes / 1024 / 1024, 2),
        },
        "primary_dataset": catalog_main,
        "legacy_dataset": legacy_main,
        "main_dataset": catalog_main,
        "samples": {
            "legacy": legacy_sample,
            "catalog": catalog_sample,
        },
        "sample": catalog_sample,
        "volume_requirement": {
            "target_rows": 500000,
            "target_megabytes": 200,
            "legacy_rows_ok": legacy_rows >= 500000,
            "legacy_megabytes_ok": legacy_bytes >= 200 * 1024 * 1024,
            "catalog_rows_ok": catalog_rows >= 500000,
            "catalog_megabytes_ok": catalog_bytes >= 200 * 1024 * 1024,
            "combined_rows_ok": data_rows >= 500000,
            "combined_megabytes_ok": data_bytes >= 200 * 1024 * 1024,
            "satisfied": data_rows >= 500000 or data_bytes >= 200 * 1024 * 1024,
        },
    }


def main() -> None:
    legacy_files = [
        file_info(path, LEGACY_SOURCES.get(path.name))
        for path in sorted(RAW_DIR.glob("*.csv"))
    ]
    catalog_files = [
        file_info(path, CATALOG_DATA_URLS.get(path.name))
        for path in sorted(CATALOG_DIR.glob("*.csv"))
    ]
    metadata_files = [
        file_info(path, CATALOG_METADATA_URLS.get(path.name), count_data_rows=False)
        for path in sorted(CATALOG_DIR.glob("*.meta.json"))
    ]
    manifest = build_manifest(legacy_files, catalog_files, metadata_files)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
