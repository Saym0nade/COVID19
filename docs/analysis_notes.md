# EDA / Time Series Notes (participant B)

Scope: descriptive statistics, missing values, IQR outliers, correlations,
resampling, rolling averages, seasonal decomposition and wave detection.
Days 4-5 added decomposition, wave detection, additional static figures and a
capped/interpretable outlier export.

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
  - `rolling_average`: grouped rolling mean, no leakage across countries
    (`min_periods=1`).
  - `seasonal_decompose`: daily aggregation + `statsmodels.tsa.seasonal` with
    period 7; returns a `SeasonalDecompositionResult` object with component
    series and JSON-serializable `to_dict`/`summary` helpers.
  - `detect_waves`: per-country hybrid of 7-day rolling mean and
    `scipy.signal.find_peaks` (details below).
- `src/visuals.py`
  - Existing `save_correlation_heatmap` (matplotlib/seaborn, PNG).
  - `save_global_trend`, `save_vaccination_rollout`, `save_waves_chart`,
    `save_outlier_boxplots` (all static matplotlib PNGs).
- `scripts/run_analysis.py`
  - Prefers `data/processed/covid_merged.parquet`, falls back to
    `data/processed/covid_clean.parquet`, then catalog/legacy sample CSV.
  - Writes `outputs/eda_summary.json`, `outputs/outliers.csv`,
    `outputs/correlation.csv`, `outputs/timeseries.csv`,
    `outputs/waves.csv` and five figures (see below).

## Wave detection method and parameters

Default call: `detect_waves(frame, value_column="new_cases_smoothed")`.

1. Keep one observation per country/date, reindex to a daily calendar and
   interpolate short reporting gaps.
2. Apply a trailing 7-day rolling mean (`rolling_window=7`) to suppress
   day-of-week/reporting spikes.
3. Detect peaks with `scipy.signal.find_peaks`:
   - `distance=30` days minimum between wave peaks;
   - `height = max(min_peak_value, prominence_ratio * country_max)` with
     `prominence_ratio=0.05`, `min_peak_value=0`;
   - `prominence = prominence_ratio * country_max` (5% of the country's largest
     smoothed value).
4. For each peak, walk left/right until the smoothed value drops to
   `onset_ratio=0.10` (10%) of that peak's value. These crossings define the
   wave start/end. Overlapping intervals are clipped so waves are disjoint and
   sequentially numbered per country.
5. Exclude OWID aggregate rows (`OWID_*` and blank codes) by default
   (`include_aggregates=False`) to avoid double counting global/regional series.

Output columns (exactly): `iso_code, location, wave_number, start_date,
end_date, peak_date, peak_value, duration_days, method`. The `method` string
records the rolling window/peak parameters so results are reproducible.

Latest run: **882 wave intervals across 231 countries**, median **4** waves per
country (min 1, max 11), median duration **92** days.

## Seasonal decomposition approach

`seasonal_decompose` aggregates the requested column to one value per day
(`agg="sum"` for case flows), reindexes the full daily calendar, linearly
interpolates internal gaps (statsmodels requires a complete series), and runs
`statsmodels.tsa.seasonal.seasonal_decompose(model="additive", period=7,
extrapolate_trend="period")`. Period 7 captures weekly reporting seasonality.
The runner applies it to the global `OWID_WRL` daily `new_cases` series and
stores only metadata and variance-based strengths in `eda_summary.json`:

- trend strength = 1 - var(resid) / var(observed)
- seasonal strength = 1 - var(resid) / var(observed - trend)

Latest run: trend strength 0.82, weekly seasonal strength 0.16. The modest
seasonal strength is expected after global aggregation; country-level series
often show stronger weekday artefacts.

## Outlier policy

`outputs/outliers.csv` is intentionally curated rather than exhaustive:

- Rule: 1.5 x IQR per column, computed on country rows only (OWID aggregates
  removed).
- Columns whose IQR is zero are skipped. `new_deaths` is largely zero-inflated
  (Q1 = Q3 = 0), so every positive value would be flagged; it is reported in
  `outliers_summary`/`outlier_policy` instead of writing ~119k rows.
- For the remaining columns, keep the **250 most severe rows per column**
  (largest distance beyond the nearest IQR bound). This caps the file while
  keeping the most extreme, interpretable observations.
- Latest run: 750 rows from 3 columns (`new_cases`,
  `new_cases_per_million`, `gdp_per_capita`); `people_vaccinated_per_hundred`
  and `human_development_index` have no IQR outliers. All policy details are
  stored in `eda_summary.json` under `outlier_policy`.

## Visualizations produced

| File | Content |
| --- | --- |
| `figures/global_cases_deaths.png` | Global smoothed daily cases and deaths (OWID_WRL). |
| `figures/vaccination_rollout_by_region.png` | Weekly mean `people_vaccinated_per_hundred` by continent. |
| `figures/waves_chart.png` | Wave intervals/peaks for the 14 largest-peak countries + number of countries in an active wave over time. |
| `figures/outliers_boxplot.png` | Symlog boxplots for the six IQR outlier columns. |
| `figures/correlation_heatmap.png` | Pearson correlation heatmap for 14 numeric features. |

## Analysis decisions

- Time-series output is weekly (`W`), grouped by `iso_code` + `location`;
  daily `new_cases` is summed per week, while `rolling_7/14/28` are daily
  rolling means sampled at the last day of each week.
- Duplicate `iso_code` + `date` rows are dropped before the time-series build
  to avoid double counting.
- Correlation uses complete numeric pairs (pairwise deletion via `corr`).
- Missing values are reported, not imputed (except interpolation internal to
  seasonal decomposition).

## Brief interpretation

- **Waves.** 2021-2022 dominates: the number of countries simultaneously inside
  a detected wave peaks at ~200 around January 2022, consistent with the
  Omicron transition. Africa contributes the most intervals (272) but has the
  shortest median duration (66 days); Europe has longer waves (median 175
  days), reflecting broader, overlapping transmission periods. The largest
  single peaks occur in China (2022-12), the United States, South Korea and
  India.
- **Vaccination.** Rollout starts in early 2021 and plateaus by late 2021 in
  Europe/North America, then catches up in Asia/South America. Africa's regional
  mean coverage stays materially lower. Coverage correlates positively with
  development proxies (`human_development_index` 0.43, `life_expectancy` 0.46,
  `gdp_per_capita` 0.36) and negatively with `stringency_index` (-0.51).
- **Mortality.** `new_deaths_per_million` is only weakly related to
  `people_vaccinated_per_hundred` (-0.11) and `people_fully_vaccinated_per_hundred`
  (-0.11); strongest positive associations are with `positive_rate` (0.20) and
  `new_cases_per_million` (0.21). These are pooled cross-sectional
  correlations, not causal effects, and are confounded by time, testing and
  reporting differences.

## Known limitations

- Rolling averages use `min_periods=1`, so the first days of each country are
  partial windows.
- Wave boundaries are amplitude-based (10% of peak) rather than epidemiological
  model estimates; low-count and sparse-reporting countries produce noisier
  intervals.
- Cumulative totals are highly trended; prefer per-million / daily flows for
  correlation interpretation.
- The merged dataset extends beyond the observed pandemic period with long zero
  tails, which flatten global trend plots after 2023.
- Heatmap annotations may be dense when many features are correlated; reduce
  `CORRELATION_COLUMNS` or set `annot=False` if needed.
