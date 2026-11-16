# Forecast notes (participant C)

Scope: global daily `new_cases_smoothed` plus the top-5 countries by latest
cumulative `total_cases`, using a time-based split and a 30-day forecast horizon.

## Series selection

- Target: `new_cases_smoothed` (daily, 7-day smoothed).
- Source priority: `data/processed/covid_merged.parquet`, then
  `data/sample/owid-catalog-sample.csv`, then `data/sample/owid-covid-sample.csv`.
- Series names in outputs:
  - `global` — sum of country-level `new_cases_smoothed` by date;
  - `country:USA`, `country:CHN`, `country:IND`, `country:FRA`, `country:DEU` —
    top-5 countries by their latest non-null `total_cases`.
- Aggregates are excluded everywhere: rows with an `iso_code` starting with
  `OWID_`, the `World` row and rows without an ISO code (for example
  `Asia excl. China`). If no country-level target values exist, the `World` row
  is used as a global fallback.
- "Latest `total_cases`" is the last non-null cumulative observation per
  country, not necessarily the dataset's final calendar date. This keeps the
  ranking stable when the final date has gaps.
- A country's target series is built from all available non-null
  `new_cases_smoothed` observations for that ISO code. Some countries have target
  data that ends earlier than their cumulative totals; the split is applied to
  the available target series and the resulting dates are exported in metrics.

Current merged-parquet run:

| Series | Latest date in target series | Latest `total_cases` |
|---|---|---:|
| `global` | 2026-10-18 | — |
| `country:USA` | 2023-05-21 | 103,436,829 |
| `country:CHN` | 2026-10-18 | 99,381,761 |
| `country:IND` | 2026-10-18 | 45,056,221 |
| `country:FRA` | 2023-07-02 | 39,064,913 |
| `country:DEU` | 2023-07-10 | 38,437,953 |

## Split and horizon

- Time-based split only: train is everything up to `test_days` before the last
  available date of each series; test is the final `test_days` calendar days.
- Defaults: `--test-days 90`, `--horizon 30`.
- Evaluation and prediction exports use the first `min(horizon, len(test))` days
  after the train cutoff, so the 30-day horizon is comparable across series.
- Run: `.venv/bin/python scripts/run_forecast.py`
  (optional flags: `--test-days`, `--horizon`, `--season-length`, `--window`,
  `--top-n`).

## Models

- `naive` — repeat the last observed value.
- `seasonal_naive` — repeat the last 7 observations.
- `moving_average` — mean of the last 7 observations, flat forecast.
- `linear_regression` — SciPy `linregress` on a time index, extrapolated and
  clipped at zero.

## Metrics and outputs

- `evaluate_mae` and `evaluate_rmse` ignore missing pairs.
- `benchmark` records per model: MAE, RMSE, fit seconds, predict seconds and peak
  Python memory (`tracemalloc`). Peak memory excludes data loading.
- `outputs/forecast_metrics.csv` — one row per series/model with `series`,
  `model`, `mae`, `rmse`, `fit_seconds`, `predict_seconds`, `peak_memory_mb`,
  `train_start`, `train_end`, `test_start`, `test_end`.
- `outputs/forecast_predictions.csv` — `series`, `date`, `actual`, `predicted`,
  `model`, `split` on the test window. Both schemas are unchanged from days 1-3;
  only the number of series grows.

## Measured time and memory

On the merged parquet (single local run, 6 series × 4 models):

- wall time: about 2.0 seconds;
- process peak RSS: about 353 MB (includes loading the full merged parquet);
- per-model peak Python memory from `tracemalloc`: about 0.07-0.16 MB;
- fit/predict time per model: below 4 ms.

## Decisions and limitations

- The global aggregation uses country rows only to avoid double counting.
- No imputation is applied to target gaps; series end at their last valid target
  observation.
- A flat moving-average forecast is a transparent baseline; no recursive updates.
- Linear regression is sensitive to trend and performs poorly on declining or
  flat epidemic tails, which is visible in the MAE table.
- The dashboard reads forecast CSVs only if they exist, so it still runs before
  forecasts are generated.
