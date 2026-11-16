from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html

try:
    from .analytics import add_derived_fields
    from .config import (
        CATALOG_SAMPLE_PATH,
        LEGACY_SAMPLE_PATH,
        MERGED_DATA_PATH,
        OUTPUTS_DIR,
        QUERIES_PATH,
    )
except ImportError:
    from analytics import add_derived_fields
    from config import (
        CATALOG_SAMPLE_PATH,
        LEGACY_SAMPLE_PATH,
        MERGED_DATA_PATH,
        OUTPUTS_DIR,
        QUERIES_PATH,
    )


METRICS = {
    "new_cases_smoothed": "New cases, 7-day smoothed",
    "new_deaths_smoothed": "New deaths, 7-day smoothed",
    "people_vaccinated_per_hundred": "Vaccinated per 100 people",
}
PREVIEW_COLUMNS = [
    "date",
    "iso_code",
    "location",
    "region",
    "category",
    "new_cases_smoothed",
    "new_deaths_smoothed",
    "total_cases",
    "total_deaths",
    "people_vaccinated_per_hundred",
]
WAVE_COLUMNS = [
    "iso_code",
    "location",
    "wave_number",
    "start_date",
    "end_date",
    "peak_date",
    "peak_value",
]
CARD_STYLE = {
    "flex": "1",
    "minWidth": "140px",
    "padding": "12px",
    "background": "#f5f7fa",
    "borderRadius": "8px",
}
TABLE_STYLE = {
    "borderCollapse": "collapse",
    "fontSize": "12px",
    "width": "100%",
}
CELL_STYLE = {"border": "1px solid #d9e0e8", "padding": "4px 8px"}
MESSAGE_STYLE = {"marginTop": "12px", "color": "#666"}


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def load_dashboard_data(path=None) -> pd.DataFrame:
    candidates = [path] if path is not None else [
        MERGED_DATA_PATH,
        CATALOG_SAMPLE_PATH,
        LEGACY_SAMPLE_PATH,
    ]
    last_error = None
    frame = None
    for candidate in candidates:
        try:
            frame = _read_frame(Path(candidate))
            break
        except (FileNotFoundError, OSError, ValueError, ImportError) as exc:
            last_error = exc
    if frame is None:
        raise FileNotFoundError(
            f"Dashboard data not found: {candidates}. "
            "Run: python scripts/build_merged_dataset.py"
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
    if "series" not in frame.columns:
        frame["series"] = "global"
    return frame


def load_forecast_predictions(path: Path | None = None) -> pd.DataFrame | None:
    """Load optional forecast predictions, returning None if unavailable."""
    predictions_path = (
        Path(path) if path is not None else OUTPUTS_DIR / "forecast_predictions.csv"
    )
    try:
        frame = pd.read_csv(predictions_path)
    except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError):
        return None
    required = {"date", "actual", "predicted", "model"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    if "series" not in frame.columns:
        frame["series"] = "global"
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    return frame if not frame.empty else None


def load_waves(path: Path | None = None) -> pd.DataFrame | None:
    """Load optional wave detection output, returning None if unavailable."""
    waves_path = Path(path) if path is not None else OUTPUTS_DIR / "waves.csv"
    try:
        frame = pd.read_csv(waves_path)
    except (FileNotFoundError, OSError, ValueError, pd.errors.EmptyDataError):
        return None
    return frame if not frame.empty else None


def _split_sql_queries(text: str) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    title = "Query"
    buffer: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            comment = stripped.lstrip("-").strip()
            if comment and not buffer:
                title = comment
            continue
        if not stripped:
            if buffer:
                buffer.append("")
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            query = "\n".join(buffer).strip()
            if query:
                queries.append((title, query))
            buffer = []
            title = "Query"
    if buffer:
        query = "\n".join(buffer).strip()
        if query:
            queries.append((title, query))
    return queries


def load_sql_queries(path: Path | None = None) -> list[tuple[str, str]] | None:
    """Load and split the project SQL queries, returning None if unavailable."""
    queries_path = Path(path) if path is not None else QUERIES_PATH
    try:
        text = queries_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    queries = _split_sql_queries(text)
    return queries or None


def load_sql_outputs(directory: Path | None = None) -> dict[str, pd.DataFrame] | None:
    """Load optional CSV outputs from executed SQL queries."""
    output_dir = Path(directory) if directory is not None else OUTPUTS_DIR / "sql"
    try:
        paths = sorted(output_dir.glob("*.csv"))
    except OSError:
        return None
    results: dict[str, pd.DataFrame] = {}
    for path in paths:
        try:
            frame = pd.read_csv(path)
        except (OSError, ValueError, pd.errors.EmptyDataError):
            continue
        if not frame.empty:
            results[path.name] = frame
    return results or None


def _format_date(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return "n/a"


def _format_number(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "n/a"


def _format_cell(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _dataframe_table(
    frame: pd.DataFrame | None,
    columns: list[str] | None = None,
    max_rows: int = 50,
    note: str | None = None,
):
    if frame is None or frame.empty:
        return html.Div(note or "No rows available.", style=MESSAGE_STYLE)
    selected = columns or list(frame.columns[:12])
    selected = [column for column in selected if column in frame.columns]
    if not selected:
        selected = list(frame.columns[:12])
    view = frame[selected].head(max_rows)
    header = html.Thead(
        html.Tr([html.Th(str(column), style=CELL_STYLE) for column in selected])
    )
    body = html.Tbody(
        [
            html.Tr([html.Td(_format_cell(value), style=CELL_STYLE) for value in row])
            for row in view.itertuples(index=False, name=None)
        ]
    )
    return html.Div(
        [
            html.Div(
                html.Table([header, body], style=TABLE_STYLE),
                style={"overflowX": "auto"},
            ),
            html.Div(
                f"Showing {len(view):,} of {len(frame):,} rows"
                + (f" - {note}" if note else ""),
                style={"fontSize": "11px", "color": "#666", "marginTop": "4px"},
            ),
        ]
    )


def _empty_figure(message: str):
    return px.line(title=message)


def _kpi_cards(frame: pd.DataFrame) -> list:
    if frame.empty:
        return [html.Div("No data for selected filters", style={"color": "#b00020"})]
    dates = frame["date"].dropna()
    latest = dates.max() if not dates.empty else None
    snapshot = frame[frame["date"] == latest] if latest is not None else frame.iloc[0:0]
    locations = frame["location"].nunique() if "location" in frame else 0
    total_cases = (
        snapshot["total_cases"].sum(min_count=1)
        if "total_cases" in snapshot
        else float("nan")
    )
    total_deaths = (
        snapshot["total_deaths"].sum(min_count=1)
        if "total_deaths" in snapshot
        else float("nan")
    )
    cards = [
        ("Rows", f"{len(frame):,}"),
        ("Locations", f"{locations:,}"),
        ("Latest date", _format_date(latest)),
        ("Total cases (latest)", _format_number(total_cases)),
        ("Total deaths (latest)", _format_number(total_deaths)),
    ]
    return [
        html.Div(
            [
                html.Div(label, style={"fontSize": "12px", "color": "#666"}),
                html.Div(
                    value,
                    style={"fontSize": "20px", "fontWeight": "600"},
                ),
            ],
            style=CARD_STYLE,
        )
        for label, value in cards
    ]


def _select_display_model(
    series_name: str,
    candidates: pd.DataFrame,
    metrics: pd.DataFrame | None,
    reference_mean: float,
    require_variance: bool = False,
) -> str | None:
    if metrics is not None and {"series", "model", "mae"}.issubset(metrics.columns):
        ordered = (
            metrics[metrics["series"] == series_name]
            .sort_values("mae")["model"]
            .dropna()
            .astype(str)
            .tolist()
        )
    else:
        ordered = candidates["model"].dropna().astype(str).unique().tolist()
    threshold = max(0.0, 0.01 * float(reference_mean))
    visible: list[tuple[str, pd.Series]] = []
    for model in ordered:
        subset = candidates[candidates["model"].astype(str) == model]
        values = pd.to_numeric(subset["predicted"], errors="coerce").dropna()
        if values.empty:
            continue
        if abs(float(values.sum())) > 0 and float(values.mean()) > threshold:
            visible.append((model, values))
    if require_variance:
        for model, values in visible:
            mean = abs(float(values.mean()))
            if float(values.std(ddof=0)) > max(1e-9, 0.01 * mean):
                return model
    return visible[0][0] if visible else None


def _forecast_section(
    metrics: pd.DataFrame | None,
    predictions: pd.DataFrame | None,
):
    if metrics is None and predictions is None:
        return html.Div(
            "Forecast outputs not found yet. Run: python scripts/run_forecast.py",
            style=MESSAGE_STYLE,
        )

    children: list = [html.H2("Forecast evaluation")]
    if metrics is not None:
        children.extend(
            [
                html.P(
                    "MAE / RMSE for the 30-day time-based holdout (lower is better). "
                    "Models include naive, seasonal naive, moving average, linear "
                    "regression, library Holt-Winters/ETS and a trained PyTorch LSTM.",
                    style={"color": "#555"},
                ),
                _dataframe_table(
                    metrics,
                    columns=[
                        "series",
                        "model",
                        "mae",
                        "rmse",
                        "fit_seconds",
                        "predict_seconds",
                        "peak_memory_mb",
                    ],
                    max_rows=100,
                ),
            ]
        )
    else:
        children.append(
            html.Div(
                "Forecast metrics are not available yet.",
                style=MESSAGE_STYLE,
            )
        )

    if predictions is not None:
        try:
            if "split" in predictions.columns:
                test_predictions = predictions[predictions["split"] == "test"].copy()
                future_predictions = predictions[predictions["split"] == "future"].copy()
            else:
                test_predictions = predictions.copy()
                future_predictions = predictions.iloc[0:0].copy()

            parts: list[pd.DataFrame] = []
            skipped_series: list[str] = []
            for series, group in test_predictions.groupby("series"):
                actual = (
                    group[["date", "actual"]]
                    .drop_duplicates(subset=["date"])
                    .rename(columns={"actual": "value"})
                )
                actual_values = pd.to_numeric(actual["value"], errors="coerce").dropna()
                reference_mean = float(actual_values.mean()) if not actual_values.empty else 0.0
                if reference_mean <= 0:
                    skipped_series.append(str(series))
                    continue
                model = _select_display_model(str(series), group, metrics, reference_mean)
                if model is None:
                    skipped_series.append(str(series))
                    continue
                actual["variable"] = "Actual"
                actual["series"] = str(series)
                predicted = group[group["model"].astype(str) == model].copy()
                predicted["variable"] = model
                predicted["series"] = str(series)
                predicted = predicted.rename(columns={"predicted": "value"})
                parts.append(actual[["date", "value", "variable", "series"]])
                parts.append(predicted[["date", "value", "variable", "series"]])

            long = pd.concat(parts, ignore_index=True).dropna(subset=["value"])
            if long.empty:
                raise ValueError("no prediction values")
            figure = px.line(
                long,
                x="date",
                y="value",
                color="variable",
                facet_col="series",
                facet_col_wrap=2,
                title="Forecast vs actual on the test window (visible model per series)",
                labels={"value": "Daily new cases, 7-day smoothed"},
            )
            figure.update_yaxes(matches=None, showticklabels=True)
            figure.update_layout(
                margin={"l": 20, "r": 20, "t": 60, "b": 20},
                legend_title_text="Series",
                height=600,
            )
            children.extend([html.H2("Forecast vs actual"), dcc.Graph(figure=figure)])
            if skipped_series:
                children.append(
                    html.P(
                        "Omitted from the plot because the target series is all zero "
                        "or no model produces a visible forecast: "
                        + ", ".join(sorted(skipped_series)),
                        style={"color": "#666", "fontSize": "12px"},
                    )
                )
        except (KeyError, ValueError, TypeError):
            children.append(
                html.Div(
                    "Forecast predictions could not be rendered.",
                    style=MESSAGE_STYLE,
                )
            )

        if not future_predictions.empty:
            try:
                future_parts: list[pd.DataFrame] = []
                skipped_future: list[str] = []
                for series, group in future_predictions.groupby("series"):
                    recent_actual = test_predictions[
                        test_predictions["series"] == series
                    ][["date", "actual"]].drop_duplicates(subset=["date"])
                    recent_values = pd.to_numeric(
                        recent_actual["actual"], errors="coerce"
                    ).dropna()
                    reference_mean = (
                        float(recent_values.mean()) if not recent_values.empty else 0.0
                    )
                    if reference_mean <= 0:
                        skipped_future.append(str(series))
                        continue
                    model = _select_display_model(
                        str(series), group, metrics, reference_mean, require_variance=True
                    )
                    if model is None:
                        skipped_future.append(str(series))
                        continue
                    actual = recent_actual.rename(columns={"actual": "value"})
                    actual["variable"] = "Actual (recent)"
                    actual["series"] = str(series)
                    predicted = group[group["model"].astype(str) == model].copy()
                    predicted["variable"] = model
                    predicted["series"] = str(series)
                    predicted = predicted.rename(columns={"predicted": "value"})
                    future_parts.append(
                        actual[["date", "value", "variable", "series"]]
                    )
                    future_parts.append(
                        predicted[["date", "value", "variable", "series"]]
                    )
                future_long = pd.concat(future_parts, ignore_index=True).dropna(
                    subset=["value"]
                )
                if future_long.empty:
                    raise ValueError("no future prediction values")
                future_figure = px.line(
                    future_long,
                    x="date",
                    y="value",
                    color="variable",
                    facet_col="series",
                    facet_col_wrap=2,
                    title="Future forecast after each series ends (visible model per series)",
                    labels={"value": "Forecasted daily new cases, 7-day smoothed"},
                )
                future_figure.update_yaxes(matches=None, showticklabels=True)
                future_figure.update_layout(
                    margin={"l": 20, "r": 20, "t": 60, "b": 20},
                    legend_title_text="Series",
                    height=600,
                )
                future_start = future_long["date"].min()
                future_end = future_long["date"].max()
                children.extend(
                    [
                        html.H2("Future forecast"),
                        html.P(
                            f"Predictions after each series' last available target date: "
                            f"{_format_date(future_start)} — {_format_date(future_end)}. "
                            "For global/CHN/IND the future window starts after the "
                            "dataset end (2026-10-18); countries with earlier reporting "
                            "end have earlier future windows. Series with all-zero "
                            "target values are omitted.",
                            style={"color": "#555"},
                        ),
                        dcc.Graph(figure=future_figure),
                    ]
                )
                if skipped_future:
                    children.append(
                        html.P(
                            "Omitted from the future chart because the target is all "
                            "zero or no model produces a visible future forecast: "
                            + ", ".join(sorted(skipped_future)),
                            style={"color": "#666", "fontSize": "12px"},
                        )
                    )
            except (KeyError, ValueError, TypeError):
                children.append(
                    html.Div(
                        "Future forecasts could not be rendered.",
                        style=MESSAGE_STYLE,
                    )
                )
        else:
            children.append(
                html.Div(
                    "Future forecasts are not available yet. "
                    "Run: python scripts/run_forecast.py",
                    style=MESSAGE_STYLE,
                )
            )
    else:
        children.append(
            html.Div(
                "Forecast predictions are not available yet.",
                style=MESSAGE_STYLE,
            )
        )
    return html.Div(children)


def _waves_section(waves: pd.DataFrame | None):
    if waves is None:
        return html.Div(
            "Wave detection output not found yet. Run the analysis pipeline to "
            "create outputs/waves.csv.",
            style=MESSAGE_STYLE,
        )

    children: list = [html.H2("Detected COVID-19 waves")]
    try:
        location_column = next(
            (
                column
                for column in ("location", "iso_code", "country")
                if column in waves.columns
            ),
            None,
        )
        if location_column is not None:
            counts = (
                waves.groupby(location_column)
                .size()
                .reset_index(name="waves")
                .nlargest(20, "waves")
            )
            figure = px.bar(
                counts,
                x="waves",
                y=location_column,
                orientation="h",
                title="Number of detected waves by location (top 20)",
            )
            figure.update_layout(
                margin={"l": 20, "r": 20, "t": 50, "b": 20},
                yaxis_title="Location",
                xaxis_title="Detected waves",
            )
            children.append(dcc.Graph(figure=figure))
        else:
            children.append(
                html.Div(
                    "Wave file has no location column; showing raw table only.",
                    style=MESSAGE_STYLE,
                )
            )
    except (KeyError, ValueError, TypeError):
        children.append(
            html.Div("Wave chart could not be rendered.", style=MESSAGE_STYLE)
        )

    children.extend(
        [
            html.H3("Wave table"),
            _dataframe_table(waves, columns=WAVE_COLUMNS, max_rows=100),
        ]
    )
    return html.Div(children)


def _sql_section(
    queries: list[tuple[str, str]] | None,
    outputs: dict[str, pd.DataFrame] | None,
):
    children: list = [html.H2("SQL queries and outputs")]
    if queries:
        children.append(html.P("Queries from sql/queries.sql", style={"color": "#555"}))
        for index, (title, query) in enumerate(queries, start=1):
            children.append(
                html.Div(
                    [
                        html.Strong(f"{index}. {title}"),
                        html.Pre(
                            query,
                            style={
                                "overflowX": "auto",
                                "fontSize": "12px",
                                "background": "#f5f7fa",
                                "padding": "10px",
                                "borderRadius": "6px",
                            },
                        ),
                    ],
                    style={"marginBottom": "12px"},
                )
            )
    else:
        children.append(
            html.Div("sql/queries.sql not found.", style=MESSAGE_STYLE)
        )

    if outputs:
        children.append(html.H3("SQL query outputs"))
        for name, frame in outputs.items():
            children.extend(
                [
                    html.H4(name),
                    _dataframe_table(frame, max_rows=20),
                ]
            )
    else:
        children.append(
            html.Div(
                "No outputs/sql/*.csv files found yet.",
                style=MESSAGE_STYLE,
            )
        )
    return html.Div(children)


def _vaccination_figure(filtered: pd.DataFrame):
    if filtered.empty:
        return _empty_figure("No data for selected filters")
    vaccination = "people_vaccinated_per_hundred"
    mortality = "total_deaths_per_million"
    if vaccination not in filtered.columns or mortality not in filtered.columns:
        return _empty_figure("Vaccination or mortality columns are unavailable")
    latest = filtered["date"].max()
    snapshot = filtered[filtered["date"] == latest].dropna(
        subset=[vaccination, mortality]
    )
    if snapshot.empty:
        return _empty_figure("No vaccination/mortality pairs on the latest date")
    hover = "location" if "location" in snapshot.columns else None
    color = "region" if "region" in snapshot.columns else None
    figure = px.scatter(
        snapshot,
        x=vaccination,
        y=mortality,
        color=color,
        hover_name=hover,
        title=f"Vaccination vs mortality on {_format_date(latest)}",
        labels={
            vaccination: "Vaccinated per 100 people",
            mortality: "Total deaths per million",
        },
    )
    figure.update_layout(
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        legend_title_text="Region",
    )
    return figure


def build_app(
    frame: pd.DataFrame,
    forecast_metrics: pd.DataFrame | None = None,
    forecast_predictions: pd.DataFrame | None = None,
    waves: pd.DataFrame | None = None,
    sql_queries: list[tuple[str, str]] | None = None,
    sql_outputs: dict[str, pd.DataFrame] | None = None,
) -> Dash:
    if forecast_metrics is None:
        forecast_metrics = load_forecast_metrics()
    if forecast_predictions is None:
        forecast_predictions = load_forecast_predictions()
    if waves is None:
        waves = load_waves()
    if sql_queries is None:
        sql_queries = load_sql_queries()
    if sql_outputs is None:
        sql_outputs = load_sql_outputs()

    years = sorted(int(year) for year in frame["year"].dropna().unique())
    regions = sorted(frame["region"].dropna().unique())
    categories = sorted(frame["category"].dropna().unique())

    app = Dash(__name__)
    app.title = "COVID-19 Global Dynamics"

    filter_bar = html.Div(
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
    )

    overview_tab = dcc.Tab(
        label="Overview",
        children=[
            html.Div(
                [
                    html.Label("Metric"),
                    dcc.RadioItems(
                        id="metric-select",
                        options=[
                            {"label": label, "value": value}
                            for value, label in METRICS.items()
                        ],
                        value="new_cases_smoothed",
                        inline=True,
                    ),
                ],
                style={"marginTop": "16px"},
            ),
            html.Div(
                id="kpi-cards",
                style={
                    "display": "flex",
                    "gap": "12px",
                    "flexWrap": "wrap",
                    "marginTop": "16px",
                },
            ),
            dcc.Graph(id="trend-chart"),
            dcc.Graph(id="region-chart"),
        ],
    )

    vaccination_tab = dcc.Tab(
        label="Vaccination vs Mortality",
        children=[
            html.P(
                "Latest-date scatter across locations that pass the filters. "
                "Hover, zoom and box-select to inspect countries.",
                style={"color": "#555"},
            ),
            dcc.Graph(id="vaccination-chart"),
        ],
    )

    forecast_tab = dcc.Tab(
        label="Forecast",
        children=[_forecast_section(forecast_metrics, forecast_predictions)],
    )

    waves_tab = dcc.Tab(
        label="Waves",
        children=[_waves_section(waves)],
    )

    data_tab = dcc.Tab(
        label="Data/SQL",
        children=[
            html.H2("Filtered data preview"),
            html.Div(id="data-preview"),
            _sql_section(sql_queries, sql_outputs),
        ],
    )

    app.layout = html.Div(
        [
            html.H1("COVID-19 Global Dynamics"),
            html.P(
                "Interactive dashboard using the merged OWID ETL catalog + legacy "
                "GitHub data with sample fallback. Filters apply to Overview, "
                "Vaccination vs Mortality and the data preview."
            ),
            filter_bar,
            dcc.Tabs(
                [
                    overview_tab,
                    waves_tab,
                    vaccination_tab,
                    forecast_tab,
                    data_tab,
                ]
            ),
        ],
        style={
            "maxWidth": "1200px",
            "margin": "0 auto",
            "padding": "24px",
            "fontFamily": "sans-serif",
        },
    )

    @app.callback(
        Output("trend-chart", "figure"),
        Output("region-chart", "figure"),
        Output("vaccination-chart", "figure"),
        Output("kpi-cards", "children"),
        Output("data-preview", "children"),
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
        preview = _dataframe_table(
            filtered,
            columns=PREVIEW_COLUMNS,
            max_rows=50,
            note="filtered data preview",
        )
        vaccination_figure = _vaccination_figure(filtered)

        if filtered.empty:
            return (
                _empty_figure("No data for selected filters"),
                _empty_figure("No data for selected filters"),
                vaccination_figure,
                kpi,
                preview,
            )
        if metric not in filtered.columns:
            return (
                _empty_figure(f"Metric is not available: {metric}"),
                _empty_figure(f"Metric is not available: {metric}"),
                vaccination_figure,
                kpi,
                preview,
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
        return figure, region_figure, vaccination_figure, kpi, preview

    return app


def main() -> None:
    frame = load_dashboard_data()
    app = build_app(frame)
    app.run(debug=True)


if __name__ == "__main__":
    main()
