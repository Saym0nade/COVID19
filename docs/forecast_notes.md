# Forecast notes (participant C)

Scope: global daily `new_cases_smoothed` plus the top-5 countries by latest
cumulative `total_cases` that have enough non-zero target data after the 2023
cutoff. Training ends on **2023-12-31**; evaluation covers the full period from
**2024-01-01** to the dataset end, followed by a future forecast after the
dataset end.

## Series selection

- Target: `new_cases_smoothed` (daily, 7-day smoothed).
- Source priority: `data/processed/covid_merged.parquet`, then
  `data/sample/owid-catalog-sample.csv`, then `data/sample/owid-covid-sample.csv`.
- Series names in outputs:
  - `global` — sum of country-level `new_cases_smoothed` by date;
  - `country:<ISO>` — top-5 countries by latest non-null `total_cases` among
    countries with at least 30 non-null target observations after 2023-12-31
    and a positive mean target value.
- Current merged-parquet run: `country:CHN`, `country:IND`, `country:BRA`,
  `country:ITA`, `country:GBR`. This replaced the earlier USA/FRA/DEU selection
  because those countries' `new_cases_smoothed` target data ends before 2023 and
  cannot be evaluated over the full post-2023 period.
- Aggregates are excluded everywhere: rows with an `iso_code` starting with
  `OWID_`, the `World` row and rows without an ISO code (for example
  `Asia excl. China`). If no country-level target values exist, the `World` row
  is used as a global fallback.
- "Latest `total_cases`" is the last non-null cumulative observation per
  country, not necessarily the dataset's final calendar date.

Current merged-parquet run:

| Series | Train end | Evaluation period | Future period |
|---|---|---|---|
| `global` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |
| `country:CHN` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |
| `country:IND` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |
| `country:BRA` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |
| `country:ITA` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |
| `country:GBR` | 2023-12-31 | 2024-01-01 — 2026-10-18 | 2026-10-19 — 2027-01-01 |

## Split and horizon

- Default time split: train is everything up to **2023-12-31**; test is the full
  period after the cutoff through the dataset end (1,022 daily observations in
  the current run).
- `--cutoff-date` controls the cutoff; default `2023-12-31`.
- `--test-days` is a legacy alternative. If explicitly provided, it overrides the
  cutoff and uses the old "last N days as test" behavior.
- **Recent holdout:** before generating future predictions, all models are
  compared with the most recent 90 real observations. The best recent model per
  series is selected for the future chart.
- **Future forecast:** each model is refitted on the full series and predicts
  from the dataset end through **2027-01-01** (75 daily observations in the
  current run). `--future-end-date` controls the end date.
- `--future-horizon` is a legacy alternative; if provided explicitly, it
  overrides `--future-end-date`.
- Future rows are exported with `split="future"` and an empty `actual` value.
- Recent rows are exported separately with `split="recent"`.
- Run: `.venv/bin/python scripts/run_forecast.py`
  (optional flags: `--cutoff-date`, `--test-days`, `--horizon`,
  `--recent-days`, `--future-end-date`, `--future-horizon`,
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
  `train_start`, `train_end`, `test_start`, `test_end`. The test period is the
  full post-2023 period, not a 30-day window.
- `outputs/forecast_predictions.csv` — `series`, `date`, `actual`, `predicted`,
  `model`, `split`. `split` is `test` for the full post-2023 period and `future`
  for dates after the dataset end.
- `outputs/forecast_future.csv` — only `split="future"` rows for convenience.
- `outputs/forecast_recent_metrics.csv` — model comparison on the last 90 real
  observations.
- `outputs/forecast_recent_predictions.csv` — recent holdout actual vs predicted
  rows (`split="recent"`).

## Measured time and memory

On the merged parquet (single local run, 6 series × 6 models, 1,022-day test):

- wall time: about 45-60 seconds, dominated by LSTM training on the full and recent splits;
- LSTM fit time: approximately 2-7 seconds per series;
- Holt-Winters fit time: approximately 0.5-0.6 seconds per series;
- baseline models: below 4 ms per series;
- per-model `tracemalloc` peak: baselines below 0.2 MB, Holt-Winters below
  0.6 MB, LSTM up to about 83 MB for the global series.

## Decisions and limitations

- The global aggregation uses country rows only to avoid double counting.
- The post-2023 backtest is a long-horizon evaluation (1,022 days), so errors are
  much larger than in the previous 30-day holdout. This is intentional.
- Top-5 countries are filtered to those with post-2023 target data; otherwise a
  country such as USA/FRA/DEU would have no evaluation period.
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
- The future chart uses the recent-holdout comparison to choose the displayed
  model; it then shows recent actual values followed by predictions through
  2027-01-01.
- Forecast plots choose a visible model per series: the lowest-MAE model whose
  predictions are non-zero and, for the future chart, not flat. Series with an
  all-zero target or no visible forecast are omitted from plots but remain in
  metrics and prediction CSVs.
- Facet y-axes are independent (`matches=None`), so series with very different
  scales remain visible in their own panels.
