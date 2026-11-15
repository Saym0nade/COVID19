from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CATALOG_DIR = RAW_DIR / "catalog"
SAMPLE_DIR = DATA_DIR / "sample"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = ROOT / "figures"
SQL_DIR = ROOT / "sql"

RAW_DATA_PATH = RAW_DIR / "owid-covid-data.csv"
LEGACY_SAMPLE_PATH = SAMPLE_DIR / "owid-covid-sample.csv"
CATALOG_SAMPLE_PATH = SAMPLE_DIR / "owid-catalog-sample.csv"
SAMPLE_DATA_PATH = LEGACY_SAMPLE_PATH

CATALOG_COMPACT_PATH = CATALOG_DIR / "compact.csv"
CATALOG_CASES_DEATHS_PATH = CATALOG_DIR / "cases_deaths.csv"
CATALOG_EXCESS_MORTALITY_PATH = CATALOG_DIR / "excess_mortality.csv"
CATALOG_EXCESS_MORTALITY_ECONOMIST_PATH = CATALOG_DIR / "excess_mortality_economist.csv"
CATALOG_HOSPITAL_PATH = CATALOG_DIR / "hospital.csv"
CATALOG_VACCINATIONS_GLOBAL_PATH = CATALOG_DIR / "vaccinations_global.csv"
CATALOG_VACCINATIONS_AGE_PATH = CATALOG_DIR / "vaccinations_age.csv"
CATALOG_VACCINATIONS_MANUFACTURER_PATH = CATALOG_DIR / "vaccinations_manufacturer.csv"
CATALOG_VACCINATIONS_US_PATH = CATALOG_DIR / "vaccinations_us.csv"
CATALOG_TESTING_PATH = CATALOG_DIR / "testing.csv"
CATALOG_TRACKING_R_PATH = CATALOG_DIR / "tracking_r.csv"
CATALOG_GOOGLE_MOBILITY_PATH = CATALOG_DIR / "google_mobility.csv"
CATALOG_OXCGRT_POLICY_PATH = CATALOG_DIR / "oxcgrt_policy.csv"
CATALOG_YOUGOV_PATH = CATALOG_DIR / "yougov_composite.csv"
CATALOG_COVAX_PATH = CATALOG_DIR / "covax.csv"

PROCESSED_DATA_PATH = PROCESSED_DIR / "covid_clean.parquet"
MERGED_DATA_PATH = PROCESSED_DIR / "covid_merged.parquet"
DB_PATH = DATA_DIR / "covid.db"
SCHEMA_PATH = SQL_DIR / "schema.sql"
QUERIES_PATH = SQL_DIR / "queries.sql"
MANIFEST_PATH = DATA_DIR / "manifest.json"

DATE_COLUMN = "date"
COUNTRY_CODE_COLUMN = "iso_code"
LOCATION_COLUMN = "location"
REGION_COLUMN = "continent"
FILTER_COLUMNS = ("year", "region", "category")
CATALOG_RENAME = {"code": "iso_code", "country": "location"}

CORE_COLUMNS = [
    "iso_code",
    "continent",
    "location",
    "date",
    "total_cases",
    "new_cases",
    "new_cases_smoothed",
    "total_deaths",
    "new_deaths",
    "new_deaths_smoothed",
    "total_cases_per_million",
    "new_cases_per_million",
    "total_deaths_per_million",
    "new_deaths_per_million",
    "people_vaccinated",
    "people_fully_vaccinated",
    "people_vaccinated_per_hundred",
    "people_fully_vaccinated_per_hundred",
    "total_boosters",
    "population",
    "gdp_per_capita",
    "human_development_index",
]

NUMERIC_COLUMNS = [
    "total_cases",
    "new_cases",
    "new_cases_smoothed",
    "total_deaths",
    "new_deaths",
    "new_deaths_smoothed",
    "total_cases_per_million",
    "new_cases_per_million",
    "total_deaths_per_million",
    "new_deaths_per_million",
    "people_vaccinated",
    "people_fully_vaccinated",
    "people_vaccinated_per_hundred",
    "people_fully_vaccinated_per_hundred",
    "total_boosters",
    "population",
    "gdp_per_capita",
    "human_development_index",
]
