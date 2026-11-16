# EDA / Time Series Notes (Phase 1, participant B)

Scope: descriptive statistics, missing values, IQR outliers, correlations,
resampling and rolling averages. Seasonal decomposition and wave detection are
intentionally left as stubs for the next wave.

## Implementation

- `src/analytics.py`
  - `descriptive_stats`: numeric summary per column (count/missing/mean/std/quartiles).
  - `missing_report`: per-column missing counts and percentages.
  - `iqr_bounds` + `detect_outliers_iqr`: 1.5 x IQR bounds and outlier rows.
  - `outlier_summary`: aggregated IQR bounds/counts for several columns.
  - `correlation_matrix`: Pearson/Spearman/Kendall correlation on numeric columns.
  - `vaccination_mortality_summary`: coverage/mortality maxima by country or region.
- `src/timeseries.py`
  - `resample_series`: resample by date with optional country grouping; `sum`
    for flows (`new_cases`), `last` for already-smoothed values.
  - `rolling_average`: grouped rolling mean, no leakage across countries.
  - `seasonal_decompose`, `detect_waves`: stubs for Phase 2.
- `src/visuals.py`
  - Added generic `save_correlation_heatmap` (matplotlib/seaborn, PNG).
- `scripts/run_analysis.py`
  - Prefers `data/processed/covid_merged.parquet`, falls back to
    `data/processed/covid_clean.parquet`, then catalog/legacy sample CSV.
  - Writes `outputs/eda_summary.json`, `outputs/outliers.csv`,
    `outputs/correlation.csv`, `outputs/timeseries.csv` and
    `figures/correlation_heatmap.png`.

## Analysis decisions

- Outlier columns: `new_cases`, `new_deaths`, `new_cases_per_million`,
  `people_vaccinated_per_hundred`, `gdp_per_capita`, `human_development_index`.
- Time-series output is weekly (`W`), grouped by `iso_code` + `location`;
  daily `new_cases` is summed per week, while `rolling_7/14/28` are daily
  rolling means sampled at the last day of each week.
- Duplicate `iso_code` + `date` rows are dropped before the time-series build
  to avoid double counting.
- Correlation uses complete numeric pairs (pairwise deletion via `corr`).
- Missing values are reported, not imputed.

## Known limitations

- Rolling averages use `min_periods=1`, so the first days of each country are
  partial windows.
- Cumulative totals are highly trended; prefer per-million / daily flows for
  correlation interpretation.
- Heatmap annotations may be dense when many features are correlated; reduce
  `CORRELATION_COLUMNS` or set `annot=False` if needed.
