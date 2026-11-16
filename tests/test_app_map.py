from __future__ import annotations

import pandas as pd

from src.analytics import add_derived_fields
from src.app import _world_map_figure, build_app, prepare_map_data


def map_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=35, freq="D")
    rows = []
    for iso, location, base in (
        ("USA", "United States", 100.0),
        ("CAN", "Canada", 50.0),
        ("OWID_WRL", "World", 1000.0),
    ):
        for offset, date in enumerate(dates):
            rows.append(
                {
                    "iso_code": iso,
                    "location": location,
                    "continent": "North America" if iso != "OWID_WRL" else None,
                    "date": date,
                    "new_cases_smoothed": base + offset,
                    "new_deaths_smoothed": 1.0,
                    "total_cases": base * 100,
                    "total_deaths": base,
                    "people_vaccinated_per_hundred": 50.0 if iso != "OWID_WRL" else 60.0,
                    "people_fully_vaccinated_per_hundred": 40.0 if iso != "OWID_WRL" else 50.0,
                    "new_cases_smoothed_per_million": base + offset,
                    "new_deaths_smoothed_per_million": 1.0,
                    "total_cases_per_million": base * 1000,
                    "total_deaths_per_million": base * 10,
                    "stringency_index": 40.0,
                }
            )
    return add_derived_fields(pd.DataFrame(rows))


def test_prepare_map_data_filters_aggregates_and_week_aggregates():
    frame = map_frame()
    weekly, weeks, marks, ranges = prepare_map_data(frame)

    assert not weekly.empty
    assert set(weekly["iso_code"].unique()) == {"USA", "CAN"}
    assert "OWID_WRL" not in set(weekly["iso_code"])
    assert weeks
    assert marks
    assert "new_cases_smoothed_per_million" in ranges
    assert weekly.groupby("week")["iso_code"].nunique().max() == 2


def test_world_map_figure_builds_choropleth():
    weekly, weeks, _, ranges = prepare_map_data(map_frame())
    figure, label = _world_map_figure(
        weekly, weeks, ranges, "new_cases_smoothed_per_million", len(weeks) - 1
    )

    assert "New cases per million" in label
    assert figure.data
    assert len(figure.data[0].locations) == 2


def test_build_app_returns_200_and_registers_map_callbacks():
    empty_metrics = pd.DataFrame(
        columns=[
            "series",
            "model",
            "mae",
            "rmse",
            "fit_seconds",
            "predict_seconds",
            "peak_memory_mb",
        ]
    )
    empty_predictions = pd.DataFrame(
        columns=["series", "date", "actual", "predicted", "model", "split"]
    )
    app = build_app(
        map_frame(),
        forecast_metrics=empty_metrics,
        forecast_predictions=empty_predictions,
        forecast_recent_metrics=empty_metrics,
        forecast_recent_predictions=empty_predictions,
        waves=pd.DataFrame(),
        sql_queries=[],
        sql_outputs={},
    )

    response = app.server.test_client().get("/")
    assert response.status_code == 200
    assert any("world-map" in key for key in app.callback_map)
    assert any("map-week-slider" in key for key in app.callback_map)
