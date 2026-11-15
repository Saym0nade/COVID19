from __future__ import annotations

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

try:
    from .analytics import add_derived_fields
    from .config import CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH
except ImportError:
    from analytics import add_derived_fields
    from config import CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH


METRICS = {
    "new_cases_smoothed": "New cases, 7-day smoothed",
    "new_deaths_smoothed": "New deaths, 7-day smoothed",
    "people_vaccinated_per_hundred": "Vaccinated per 100 people",
}


def load_dashboard_data(path=None) -> pd.DataFrame:
    candidates = [path] if path is not None else [CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH]
    last_error = None
    for candidate in candidates:
        try:
            frame = pd.read_csv(candidate)
            break
        except FileNotFoundError as exc:
            last_error = exc
    else:
        raise FileNotFoundError(
            f"Sample data not found: {candidates}. Run: python scripts/prepare_data.py"
        ) from last_error
    frame = add_derived_fields(frame)
    return frame.dropna(subset=["date"]).copy()


def build_app(frame: pd.DataFrame) -> Dash:
    years = sorted(int(year) for year in frame["year"].dropna().unique())
    regions = sorted(frame["region"].dropna().unique())
    categories = sorted(frame["category"].dropna().unique())

    app = Dash(__name__)
    app.title = "COVID-19 Global Dynamics"

    app.layout = html.Div(
        [
            html.H1("COVID-19 Global Dynamics"),
            html.P(
                "Phase 0 dashboard shell. Primary data: OWID ETL catalog. "
                "Legacy GitHub data is kept as fallback. Filters: year, region, category."
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Year"),
                            dcc.Dropdown(
                                id="year-filter",
                                options=[{"label": str(value), "value": value} for value in years],
                                value=years,
                                multi=True,
                            ),
                        ],
                        style={"flex": "1", "minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Region"),
                            dcc.Dropdown(
                                id="region-filter",
                                options=[{"label": str(value), "value": value} for value in regions],
                                value=regions,
                                multi=True,
                            ),
                        ],
                        style={"flex": "1", "minWidth": "180px"},
                    ),
                    html.Div(
                        [
                            html.Label("Category"),
                            dcc.Dropdown(
                                id="category-filter",
                                options=[{"label": str(value), "value": value} for value in categories],
                                value=categories,
                                multi=True,
                            ),
                        ],
                        style={"flex": "1", "minWidth": "180px"},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Label("Metric"),
                    dcc.RadioItems(
                        id="metric-select",
                        options=[{"label": label, "value": value} for value, label in METRICS.items()],
                        value="new_cases_smoothed",
                        inline=True,
                    ),
                ],
                style={"marginTop": "16px"},
            ),
            dcc.Graph(id="trend-chart"),
        ],
        style={"maxWidth": "1200px", "margin": "0 auto", "padding": "24px", "fontFamily": "sans-serif"},
    )

    @app.callback(
        Output("trend-chart", "figure"),
        Input("year-filter", "value"),
        Input("region-filter", "value"),
        Input("category-filter", "value"),
        Input("metric-select", "value"),
    )
    def update_trend(years_value, regions_value, categories_value, metric):
        filtered = frame
        if years_value:
            filtered = filtered[filtered["year"].isin(years_value)]
        if regions_value:
            filtered = filtered[filtered["region"].isin(regions_value)]
        if categories_value:
            filtered = filtered[filtered["category"].isin(categories_value)]
        if filtered.empty:
            return px.line(title="No data for selected filters")
        if metric not in filtered.columns:
            return px.line(title=f"Metric is not available: {metric}")

        if metric.endswith("_per_hundred"):
            grouped = filtered.groupby(["date", "region"], as_index=False)[metric].mean()
        else:
            grouped = filtered.groupby(["date", "region"], as_index=False)[metric].sum()

        figure = px.line(
            grouped,
            x="date",
            y=metric,
            color="region",
            title=f"{METRICS[metric]} by region",
        )
        figure.update_layout(
            margin={"l": 20, "r": 20, "t": 50, "b": 20},
            legend_title_text="Region",
            xaxis_title="Date",
            yaxis_title=METRICS[metric],
        )
        return figure

    return app


def main() -> None:
    frame = load_dashboard_data()
    app = build_app(frame)
    app.run(debug=True)


if __name__ == "__main__":
    main()
