# Forecast notes (participant C, days 1-3)

Scope: global forecast baselines and forecast dashboard shell only. Top-5 country
forecasts, waves tab and the final dashboard are intentionally not implemented yet.

## Target and data

- Target: global daily `new_cases_smoothed`.
- Source priority: `data/processed/covid_merged.parquet`, then
  `data/sample/owid-catalog-sample.csv`, then `data/sample/owid-covid-sample.csv`.
- The global series aggregates country/territory rows by date. OWID aggregates
  (`iso_code` starting with `OWID_`) and the `World` row are excluded to avoid
  double counting. If only `World` rows exist, they are used as fallback.
- Run: `.venv/bin/python scripts/run_forecast.py`
  (`--test-days` default 90, `--horizon` default 30).

## Split and models

- Time-based split only: train is everything up to `test_days` before the last
  date; test is the final `test_days` calendar days. Metrics and predictions use
  the first `horizon` days of the test window (default 30).
- Baselines: naive (last value) and seasonal naive (repeat last 7 days).
- Approaches: moving average (mean of last 7 observations, flat forecast) and
  linear regression (SciPy `linregress` on a time index, extrapolated).
- Linear regression predictions are clipped at zero because the target is a count.

## Metrics and outputs

- `evaluate_mae` and `evaluate_rmse` ignore missing pairs.
- `benchmark` records MAE, RMSE, fit seconds, predict seconds and peak Python
  memory (`tracemalloc`) per model.
- `outputs/forecast_metrics.csv`: one row per model with split boundaries.
- `outputs/forecast_predictions.csv`: test-period actual vs predicted per model.

## Decisions / limitations

- Evaluation uses the first `horizon` days after the train cutoff, not the full
  90-day holdout, so the default 30-day horizon is comparable across models.
- A flat moving-average forecast is a transparent baseline; no recursive updates.
- Peak memory is measured inside `benchmark` and excludes data loading.
- The dashboard reads forecast metrics only if the CSV exists, so it still runs
  before forecasts are generated.
