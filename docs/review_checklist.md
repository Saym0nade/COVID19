# Day 7: Review checklist

## Software implementation

- [x] Python 3.x project with multiple modules.
- [x] More than 5 functions beyond `main`.
- [x] `list`/`dict` used for data and configuration.
- [x] `if`/`elif`/`else` used in validation and dashboard logic.
- [x] `for`/`while` used in loops, parsing, and menu.
- [x] File reading/writing: CSV, JSON, Parquet, SQLite.
- [x] `try/except` around data loading, database access, forecast/analysis runs.
- [x] Interactive dashboard (Dash) with filters and tabs.
- [x] Modular code in `src/`, `scripts/`, `sql/`.

## Data and preprocessing

- [x] Catalog + legacy merge with fallback.
- [x] Missing-code rows preserved.
- [x] `clean_data` deduplicates by country/date.
- [x] dtype optimization and Parquet.
- [x] data profile with rows, dates, memory and missing counts.
- [x] CSV vs Parquet benchmark with time and memory.

## Databases and SQL

- [x] Normalized SQLite schema.
- [x] ER diagram: `docs/er_diagram.md`.
- [x] 9 SQL queries with JOIN, GROUP BY/HAVING, CTE and window functions.
- [x] Query results exported to `outputs/sql/*.csv`.
- [x] `waves` table populated from analysis output.

## Data analysis and visualization

- [x] Descriptive statistics, missing report, feature types.
- [x] IQR outliers and boxplots.
- [x] Correlation matrix and heatmap.
- [x] Weekly resampling and rolling averages.
- [x] Seasonal decomposition.
- [x] Wave detection with rolling average + `find_peaks`.
- [x] 5 static figures in `figures/`.
- [x] Interactive Plotly dashboard and World Map.

## Methods, comparison, justification

- [x] Baseline: naive and seasonal naive.
- [x] Approaches: moving average, Linear Regression, Holt-Winters/ETS, LSTM.
- [x] Full post-2023 backtest.
- [x] Recent 90-day holdout comparison before future forecast.
- [x] MAE, RMSE, fit/predict time and peak memory.
- [x] Future forecast to 2027-01-01.
- [x] Time-based split without leakage.

## Code quality and reproducibility

- [x] `requirements.txt` and `requirements-dev.txt`.
- [x] `README.md` with run instructions and expected outputs.
- [x] `scripts/run_all.py` for end-to-end reproduction.
- [x] `scripts/smoke_test.py` for artifact/SQL checks.
- [x] Automated tests in `tests/`.
- [x] GitHub repository with role branches, `sync-1` and `phase-1` tags.

## Written report

- [ ] Full report still to be finalized on days 8–9.
- [x] Day 7 draft sections prepared in `report/report.md`.
- [x] Metric tables and limitations included in draft.
- [ ] Final references and screenshots to be added.

## Presentation and defense

- [ ] Presentation still to be assembled on days 8–9.
- [x] Contribution matrix drafted.
- [ ] Defense rehearsal still pending.

## Test commands

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/run_all.py
```

Expected result: pytest all tests pass; smoke test 17/17 PASS; dashboard HTTP 200.
