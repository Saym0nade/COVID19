from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

try:
    from .analytics import add_derived_fields
    from .config import CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH, OUTPUTS_DIR
except ImportError:
    from analytics import add_derived_fields
    from config import CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH, OUTPUTS_DIR


METRICS = {
    "new_cases_smoothed": "New cases, 7-day smoothed",
    "new_deaths_smoothed": "New deaths, 7-day smoothed",
    "people_vaccinated_per_hundred": "Vaccinated per 100 people",
}


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def load_dashboard_data(path=None) -> pd.DataFrame:
    candidates = [path] if path is not None else [CATALOG_SAMPLE_PATH, LEGACY_SAMPLE_PATH]
    last_error = None
    for candidate in candidates:
        try:
            frame = _read_frame(Path(candidate))
            break
        except (FileNotFoundError, OSError, ValueError) as exc:
            last_error = exc
    else:
        raise FileNotFoundError(
            f"Sample data not found: {candidates}. Run: python scripts/prepare_data.py"
        ) from last_error

    try:
        frame = add_derived_fields(frame)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Dashboard data could not be prepared") from exc

    if "date" not in frame.columns:
        raise KeyError("Dashboard data must contain a 'date' column")
    frame = frame.dropna(subset=["date"]).copy()
    if frame.empty:
        raise ValueError("Dashboard data is empty after removing invalid dates")
    return frame


def load_forecast_metrics(path: Path | None = None) -> pd.DataFrame | None:
    """Load optional forecast metrics, returning None if unavailable."""
    metrics_path = Path(path) if path is not None else OUTPUTS_DIR / "forecast_metrics.csv"
    try:
        frame = pd.read_csv(metrics_path)
    except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError):
        return None
    if frame.empty or not {"model", "mae"}.issubset(frame.columns):
        return None
    return frame


def _kpi_cards(frame: pd.DataFrame) -> list:
    if frame.empty:
        return [html.Div("No data for selected filters", style={"color": "#b00020"})]
    dates = frame["date"].dropna()
    locations = frame["location"].nunique() if "location" in frame else 0
    cards = [
        ("Rows", f"{len(frame):,}"),
        ("Locations", f"{locations:,}"),
        ("Latest date", _format_date(dates.max()) if not dates.empty else "n/a"),
    ]
    return [
        html.Div(
            [html.Div(label, style={"fontSize": "12px", "color": "#666"}), html.Div(value, style={"fontSize": "20px", "fontWeight": "600"})],
            style={"flex": "1", "minWidth": "140px", "padding": "12px", "background": "#f5f7fa", "borderRadius": "8px"},
        )
        for label, value in cards
    ]


def _format_date(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return "n/a"


def _forecast_section(metrics: pd.DataFrame | None):
    if metrics is None:
        return html.Div(
            "Forecast outputs not found yet. Run: python scripts/run_forecast.py",
            style={"marginTop": "24px", "color": "#666"},
        )

    try:
        chart_data = metrics.sort_values("mae")
        figure = px.bar(
            chart_data,
            x="model",
            y="mae",
            color="model",
            title="Forecast comparison: MAE (lower is better)",
        )
        figure.update_layout(showlegend=False, margin={"l": 20, "r": 20, "t": 50, "b": 20})
        table = metrics.to_string(index=False) if metrics is not None else ""
    except (KeyError, ValueError, TypeError):
        return html.Div("Forecast metrics could not be rendered.", style={"marginTop": "24px"})

    return html.Div(
        [
            html.H2("Forecast comparison"),
            dcc.Graph(figure=figure),
            html.Pre(table, style={"overflow": "auto", "fontSize": "12px", "background": "#f5f7fa", "padding": "12px"}),
        ],
        style={"marginTop": "24px"},
    )


def build_app(frame: pd.DataFrame, forecast_metrics: pd.DataFrame | None = None) -> Dash:
    years = sorted(int(year) for year in frame["year"].dropna().unique())
    regions = sorted(frame["region"].dropna().unique())
    categories = sorted(frame["category"].dropna().unique())

    app = Dash(__name__)
    app.title = "COVID-19 Global Dynamics"

    app.layout = html.Div(
        [
            html.H1("COVID-19 Global Dynamics"),
            html.P(
                "Dashboard shell using OWID ETL catalog sample data with legacy GitHub "
                "fallback. Filters: year, region, category."
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
            html.Div(id="kpi-cards", style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginTop": "16px"}),
            dcc.Graph(id="trend-chart"),
            dcc.Graph(id="region-chart"),
            _forecast_section(forecast_metrics),
        ],
        style={"maxWidth": "1200px", "margin": "0 auto", "padding": "24px", "fontFamily": "sans-serif"},
    )

    @app.callback(
        Output("trend-chart", "figure"),
        Output("region-chart", "figure"),
        Output("kpi-cards", "children"),
        Input("year-filter", "value"),
        Input("region-filter", "value"),
        Input("category-filter", "value"),
        Input("metric-select", "value"),
    )
    def update_dashboard(years_value, regions_value, categories_value, metric):
        filtered = frame
        if years_value:
            filtered = filtered[filtered["year"].isin(years_value)]
        if regions_value:
            filtered = filtered[filtered["region"].isin(regions_value)]
        if categories_value:
            filtered = filtered[filtered["category"].isin(categories_value)]

        kpi = _kpi_cards(filtered)
        if filtered.empty:
            return (
                px.line(title="No data for selected filters"),
                px.bar(title="No data for selected filters"),
                kpi,
            )
        if metric not in filtered.columns:
            return (
                px.line(title=f"Metric is not available: {metric}"),
                px.bar(title=f"Metric is not available: {metric}"),
                kpi,
            )

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

        latest = filtered["date"].max()
        snapshot = filtered[filtered["date"] == latest].copy()
        if metric.endswith("_per_hundred"):
            snapshot = snapshot.groupby("location", as_index=False)[metric].mean()
        else:
            snapshot = snapshot.groupby("location", as_index=False)[metric].sum()
        snapshot = snapshot.nlargest(10, metric).sort_values(metric)
        region_figure = px.bar(
            snapshot,
            x=metric,
            y="location",
            orientation="h",
            title=f"Top locations: {METRICS[metric]} on {_format_date(latest)}",
        )
        region_figure.update_layout(
            margin={"l": 20, "r": 20, "t": 50, "b": 20},
            xaxis_title=METRICS[metric],
            yaxis_title="Location",
        )
        return figure, region_figure, kpi

    return app


def main() -> None:
    frame = load_dashboard_data()
    app = build_app(frame, load_forecast_metrics())
    app.run(debug=True)


if __name__ == "__main__":
    main()
