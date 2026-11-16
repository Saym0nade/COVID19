# Day 6: Integration report

## Status

End-to-end integration completed successfully.

Command:

```bash
.venv/bin/python scripts/run_all.py
```

The runner executes:

1. `scripts/prepare_data.py`
2. `scripts/build_merged_dataset.py`
3. `scripts/run_analysis.py`
4. `scripts/build_sqlite.py`
5. `scripts/run_sql.py`
6. `scripts/run_forecast.py`
7. `scripts/benchmark_storage.py`
8. `scripts/smoke_test.py`
9. Dash HTTP smoke check

## Integration results

### Data

- merged Parquet: **624,273 rows × 67 columns**;
- date range: **2020-01-01 — 2026-10-18**;
- memory after optimization: **211.73 MB** (337.21 MB before optimization);
- data profile: `outputs/data_profile.json`.

### Analysis

- EDA summary: `outputs/eda_summary.json`;
- outliers: **750 rows** across 3 informative columns;
- correlations: **91 pairs** across 14 features;
- weekly time series: **89,386 rows**;
- detected waves: **882 intervals** across **231 countries**;
- figures generated: 5 PNG files in `figures/`.

### Database and SQL

SQLite tables:

| Table | Rows |
|---|---:|
| `countries` | 257 |
| `covid_metrics` | 610,948 |
| `vaccinations` | 85,830 |
| `excess_mortality` | 13,926 |
| `waves` | 882 |

SQL queries: **9/9 succeeded**.

### Forecast

- training cutoff: **2023-12-31**;
- full evaluation: **2024-01-01 — 2026-10-18** (1,022 days);
- recent holdout: last **90 days**;
- future horizon: **2026-10-19 — 2027-01-01**;
- series: `global`, `country:CHN`, `country:IND`, `country:BRA`, `country:ITA`, `country:GBR`;
- models: naive, seasonal naive, moving average, Linear Regression, Holt-Winters/ETS, LSTM.

Outputs:

- `outputs/forecast_metrics.csv`;
- `outputs/forecast_predictions.csv`;
- `outputs/forecast_future.csv`;
- `outputs/forecast_recent_metrics.csv`;
- `outputs/forecast_recent_predictions.csv`.

### Performance

CSV vs Parquet on the same legacy OWID data:

- CSV: **0.418 s**, peak **89.47 MB**, file **93.83 MB**;
- Parquet: **0.064 s**, peak **59.51 MB**, file **5.45 MB**;
- speedup: **6.53x**.

### Smoke test

`scripts/smoke_test.py`:

- checks passed: **17**;
- warnings: **0**;
- failed: **0**;
- result: **PASS**.

### Dashboard

- HTTP status: **200**;
- tabs: Overview, World Map, Waves, Vaccination vs Mortality, Forecast, Data/SQL;
- World Map: weekly choropleth + metric selector + slider + Play/Pause;
- map data: **355 weeks**, about **83k country-week rows**.

## Fixes made during integration

- wave intervals are loaded into the SQLite `waves` table from `outputs/waves.csv`;
- the dashboard forecast tab reads recent holdout and future outputs safely;
- vaccination/coverage map metrics use forward-fill so recent weeks are not empty;
- count metrics use nearest-available-week fallback for stringency;
- `clean_data` keeps the last duplicate country/date row;
- forecast frequency handling is future-pandas compatible;
- forecast and analysis runners now report clear errors instead of raw tracebacks.
