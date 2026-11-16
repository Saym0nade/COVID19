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
- **Future forecast:** each model is refitted on the full series and predicts
  `--future-horizon` days after the last available target date of that series.
  The default is 30 days. For `global`, `country:CHN` and `country:IND` this is
  after the dataset end (2026-10-18); USA/FRA/DEU have target data ending
  earlier, so their future windows start earlier. Future rows are exported with
  `split="future"` and an empty `actual` value.
- Run: `.venv/bin/python scripts/run_forecast.py`
  (optional flags: `--test-days`, `--horizon`, `--future-horizon`,
  `--season-length`, `--window`, `--top-n`, `--lstm-lookback`,
  `--lstm-hidden`, `--lstm-epochs`, `--seed`).

## Models

- `naive` — repeat the last observed value.
- `seasonal_naive` — repeat the last 7 observations.
- `moving_average` — mean of the last 7 observations, flat forecast.
- `linear_regression` — SciPy `linregress` on a time index, extrapolated and
  clipped at zero.
- `holt_winters` — library-provided `statsmodels` Holt-Winters / Exponential
  Smoothing with additive trend, additive weekly seasonality and damped trend.
  This is the "ready-made" model loaded from a library rather than implemented
  from scratch.
- `lstm` — trainable PyTorch LSTM trained on sliding windows of the target
  series. Defaults: lookback 30 days, hidden size 32, 40 epochs, Adam,
  batch size 32, fixed seed 42. The series is transformed with `log1p` and
  min-max scaled; predictions are clipped to the historical range.

## Metrics and outputs

- `evaluate_mae` and `evaluate_rmse` ignore missing pairs.
- `benchmark` records per model: MAE, RMSE, fit seconds, predict seconds and peak
  Python memory (`tracemalloc`). Peak memory excludes data loading.
- `outputs/forecast_metrics.csv` — one row per series/model with `series`,
  `model`, `mae`, `rmse`, `fit_seconds`, `predict_seconds`, `peak_memory_mb`,
  `train_start`, `train_end`, `test_start`, `test_end`.
- `outputs/forecast_predictions.csv` — `series`, `date`, `actual`, `predicted`,
  `model`, `split`. `split` is `test` for the holdout and `future` for dates
  after the dataset ends.
- `outputs/forecast_future.csv` — only `split="future"` rows for convenience.
- `outputs/forecast_metrics.csv` schema is unchanged: `series`, `model`, `mae`,
  `rmse`, `fit_seconds`, `predict_seconds`, `peak_memory_mb`, `train_start`,
  `train_end`, `test_start`, `test_end`.

## Measured time and memory

On the merged parquet (single local run, 6 series × 6 models):

- wall time: about 35-45 seconds, dominated by LSTM training;
- LSTM fit time: approximately 2-10 seconds per series;
- Holt-Winters fit time: approximately 0.5-0.8 seconds per series;
- baseline models: below 4 ms per series;
- per-model `tracemalloc` peak: baselines below 0.2 MB, Holt-Winters below
  0.6 MB, LSTM up to about 83 MB for the global series.

## Decisions and limitations

- The global aggregation uses country rows only to avoid double counting.
- No imputation is applied to target gaps; series end at their last valid target
  observation.
- A flat moving-average forecast is a transparent baseline; no recursive updates.
- Linear regression is sensitive to trend and performs poorly on declining or
  flat epidemic tails, which is visible in the MAE table.
- LSTM is trained from scratch on each series and is intentionally a trainable
  comparison model, not a tuned production model.
- Holt-Winters is the library-provided "ready-made" approach; it is fitted
  automatically by `statsmodels`.
- The dashboard reads forecast CSVs only if they exist, so it still runs before
  forecasts are generated. Future rows are rendered in a separate chart.
- Forecast plots choose a visible model per series: the lowest-MAE model whose
  predictions are non-zero and, for the future chart, not flat. Series with an
  all-zero target (for example CHN/IND) are omitted from plots so that panels are
  not empty; they remain in metrics and prediction CSVs.
- Facet y-axes are independent (`matches=None`), so series with very different
  scales remain visible in their own panels.
