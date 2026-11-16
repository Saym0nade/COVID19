# World Map notes

## Purpose

The **World Map** tab shows country-level statistics as a weekly choropleth
heatmap with a time slider and Play/Pause controls.

## Data source and filtering

- Source priority: `data/processed/covid_merged.parquet`, then catalog sample,
  then legacy sample.
- Only real countries are kept:
  - `iso_code` has length 3;
  - `iso_code` does not start with `OWID_`;
  - `date` is valid.
- `World`, continents, income groups and other aggregates are excluded.
- The main dashboard `year`/`region`/`category` filters do **not** apply to the
  map; the map has its own metric and week controls.

## Weekly aggregation

Daily observations are grouped by ISO week (`W-SUN`, week start Monday).

| Metric | Aggregation |
|---|---|
| `new_cases_smoothed_per_million` | weekly mean |
| `new_deaths_smoothed_per_million` | weekly mean |
| `total_cases_per_million` | last value in week |
| `total_deaths_per_million` | last value in week |
| `people_vaccinated_per_hundred` | last value in week |
| `people_fully_vaccinated_per_hundred` | last value in week |
| `stringency_index` | weekly mean |

For cumulative/coverage metrics (`total_*_per_million`,
`people_*_per_hundred`), the weekly value is forward-filled within each country,
so the map shows the last known value after reporting ends. Flow metrics
(`new_*`) are not forward-filled. Stringency is not forward-filled; if the
selected week has no stringency data, the map shows the nearest earlier
available week.

The result is a compact long/wide frame with one row per country-week. In the
current merged dataset this is about **83k rows** and **355 weeks**.

## Color scale

- Cases/deaths metrics use robust 2nd–98th percentile ranges across all weeks.
- Vaccination and stringency use a fixed `0–100` range.
- Keeping the range stable across weeks prevents color flicker while moving the
  slider.
- Countries without a value for the selected week are grey.

## Controls

- Metric dropdown: per-million cases/deaths, cumulative per-million cases/deaths,
  vaccination coverage and stringency.
- Week slider: weekly index with marks roughly every six months.
- Play/Pause: advances the slider every 700 ms and loops at the end.
- Hover: country, week, metric value and continent.

## Implementation

- `prepare_map_data(frame)` builds the weekly map frame once at app startup.
- `_world_map_figure(...)` builds one weekly choropleth per callback.
- Dash callbacks:
  - metric + slider -> map figure + week label;
  - Play button -> playing state + interval enabled/disabled;
  - Interval -> next slider value.
- Plotly `px.choropleth` with `locationmode="ISO-3"` is used; no extra
  geographic dependency is required.

## Limitations

- Some countries have missing values in individual weeks; those weeks show grey
  for flow metrics.
- Vaccination and stringency coverage starts later than cases/deaths.
- Cumulative/coverage metrics use forward-fill, so a country may show its last
  known value rather than a fresh observation for that week.
- Stringency can display an earlier week with the "nearest available week" note.
- ISO-3 matching relies on OWID `iso_code` values; invalid/non-ISO codes are
  filtered out.
- Weekly aggregation smooths short daily spikes.
