from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def line_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
) -> go.Figure:
    return px.line(frame, x=x, y=y, color=color, title=title)


def heatmap(frame: pd.DataFrame, title: str = "") -> go.Figure:
    return px.imshow(frame, text_auto=True, aspect="auto", title=title)


def boxplot(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
) -> go.Figure:
    return px.box(frame, x=x, y=y, title=title)


def save_correlation_heatmap(
    matrix: pd.DataFrame,
    path: Path,
    title: str = "Correlation heatmap",
    figsize: tuple[float, float] = (14.0, 12.0),
    annot: bool = True,
    cmap: str = "coolwarm",
) -> Path | None:
    """Save a static correlation heatmap using matplotlib/seaborn.

    Returns the written path, or ``None`` when the optional libraries are not
    installed or the matrix is empty.
    """
    if matrix is None or matrix.empty:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return None

    width = max(figsize[0], 0.6 * len(matrix.columns) + 4)
    height = max(figsize[1], 0.5 * len(matrix.index) + 4)
    figure, axes = plt.subplots(figsize=(width, height))
    sns.heatmap(
        matrix,
        annot=annot,
        fmt=".2f",
        cmap=cmap,
        vmin=-1.0,
        vmax=1.0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8},
        ax=axes,
    )
    axes.set_title(title)
    figure.tight_layout()

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return destination


def _load_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _prepare_destination(path: Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def save_global_trend(
    frame: pd.DataFrame,
    path: Path,
    date_column: str = "date",
    title: str = "Global COVID-19 cases and deaths",
) -> Path | None:
    """Plot global daily cases and deaths (two panels) as a static PNG.

    Uses the OWID ``OWID_WRL`` aggregate when available to avoid double
    counting; otherwise sums non-aggregate countries per day and resamples
    weekly. Already-smoothed columns are preferred when present.
    """
    if date_column not in frame.columns:
        return None
    plt = _load_pyplot()

    work = frame.copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work = work.dropna(subset=[date_column])
    cases_column = (
        "new_cases_smoothed"
        if "new_cases_smoothed" in work.columns
        else "new_cases"
    )
    deaths_column = (
        "new_deaths_smoothed"
        if "new_deaths_smoothed" in work.columns
        else "new_deaths"
    )
    if cases_column not in work.columns or deaths_column not in work.columns:
        return None

    iso = work.get("iso_code")
    global_rows = (
        work.loc[iso.astype("string") == "OWID_WRL"]
        if iso is not None
        else pd.DataFrame()
    )
    if not global_rows.empty:
        trend = (
            global_rows[[date_column, cases_column, deaths_column]]
            .sort_values(date_column)
            .drop_duplicates(subset=[date_column], keep="last")
            .set_index(date_column)
        )
    else:
        if iso is not None:
            work = work[~iso.astype("string").str.startswith("OWID_", na=False)]
        weekly = (
            work.groupby(pd.Grouper(key=date_column, freq="W"))[[cases_column, deaths_column]]
            .sum(min_count=1)
        )
        trend = weekly

    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(trend.index, trend[cases_column], color="#1f77b4", linewidth=1.2)
    axes[0].set_ylabel("New cases (smoothed)")
    axes[0].set_title(title)
    axes[0].grid(alpha=0.25)
    axes[1].plot(trend.index, trend[deaths_column], color="#d62728", linewidth=1.2)
    axes[1].set_ylabel("New deaths (smoothed)")
    axes[1].set_xlabel("Date")
    axes[1].grid(alpha=0.25)
    figure.tight_layout()

    destination = _prepare_destination(path)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return destination


def save_vaccination_rollout(
    frame: pd.DataFrame,
    path: Path,
    date_column: str = "date",
    value_column: str = "people_vaccinated_per_hundred",
    region_column: str = "continent",
    title: str = "Vaccination rollout by region",
) -> Path | None:
    """Plot mean vaccination coverage per region over time (weekly)."""
    needed = [date_column, value_column, region_column]
    if any(column not in frame.columns for column in needed):
        return None
    plt = _load_pyplot()

    work = frame[needed].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
    work[region_column] = work[region_column].astype("string")
    work = work.dropna(subset=[date_column, value_column, region_column])
    work = work[~work[region_column].isin(["Unknown", ""])]
    if work.empty:
        return None

    weekly = (
        work.groupby([region_column, pd.Grouper(key=date_column, freq="W")])[value_column]
        .mean()
        .reset_index()
    )

    figure, axes = plt.subplots(figsize=(12, 7))
    for region, group in weekly.groupby(region_column, observed=True):
        axes.plot(
            group[date_column],
            group[value_column],
            label=str(region),
            linewidth=1.8,
        )
    axes.set_title(title)
    axes.set_ylabel("People vaccinated per 100 (regional mean)")
    axes.set_xlabel("Date")
    axes.grid(alpha=0.25)
    axes.legend(title="Region", fontsize=8, ncol=2)
    figure.tight_layout()

    destination = _prepare_destination(path)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return destination


def save_waves_chart(
    waves: pd.DataFrame,
    frame: pd.DataFrame,
    path: Path,
    title: str = "Detected COVID-19 waves",
    top_countries: int = 14,
) -> Path | None:
    """Visualise wave intervals for the largest waves and global activity.

    Left panel: horizontal wave intervals (one row per country) with peak
    markers for the ``top_countries`` countries with the highest peak values.
    Right panel: number of countries simultaneously inside a detected wave.
    """
    if waves is None or waves.empty:
        return None
    plt = _load_pyplot()
    import matplotlib.dates as mdates

    work = waves.copy()
    for column in ("start_date", "end_date", "peak_date"):
        work[column] = pd.to_datetime(work[column], errors="coerce")
    work = work.dropna(subset=["start_date", "end_date", "peak_date"])
    if work.empty:
        return None

    ranked = (
        work.groupby(["iso_code", "location"], observed=True)["peak_value"]
        .max()
        .sort_values(ascending=False)
    )
    selected = ranked.index[:top_countries].tolist()
    subset = work.set_index(["iso_code", "location"]).loc[selected].reset_index()
    order = [label for label in selected if label in set(zip(subset["iso_code"], subset["location"]))]

    figure, axes = plt.subplots(
        1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [2.1, 1.0]}
    )

    labels = [f"{iso} - {location}" for iso, location in order]
    y_positions = {label: index for index, label in enumerate(labels)}
    cmap = plt.get_cmap("tab20")
    for row in subset.itertuples(index=False):
        label = f"{row.iso_code} - {row.location}"
        y = y_positions.get(label)
        if y is None:
            continue
        axes[0].barh(
            y,
            (row.end_date - row.start_date).days + 1,
            left=row.start_date,
            height=0.6,
            color=cmap((int(row.wave_number) - 1) % 20),
            alpha=0.75,
        )
        axes[0].plot(row.peak_date, y, marker="v", color="black", markersize=4)
    axes[0].set_yticks(range(len(labels)))
    axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].invert_yaxis()
    axes[0].set_title("Wave intervals for countries with the largest peaks")
    axes[0].set_xlabel("Date")
    axes[0].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[0].xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
    axes[0].grid(axis="x", alpha=0.25)

    first = work["start_date"].min().normalize()
    last = work["end_date"].max().normalize()
    daily_index = pd.date_range(first, last, freq="D")
    active = pd.Series(0, index=daily_index, dtype="int64")
    for row in work.itertuples(index=False):
        active.loc[row.start_date : row.end_date] += 1
    axes[1].fill_between(active.index, active.to_numpy(), color="#ff7f0e", alpha=0.6)
    axes[1].set_title("Countries in an active wave")
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Countries")
    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
    axes[1].grid(alpha=0.25)

    figure.suptitle(title)
    figure.tight_layout()

    destination = _prepare_destination(path)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return destination


def save_outlier_boxplots(
    frame: pd.DataFrame,
    columns: list[str],
    path: Path,
    title: str = "Distributions used for IQR outlier detection",
) -> Path | None:
    """Small-multiple boxplots (symlog y-axis) for the outlier columns."""
    available = [
        column
        for column in columns
        if column in frame.columns and pd.to_numeric(frame[column], errors="coerce").notna().any()
    ]
    if not available:
        return None
    plt = _load_pyplot()
    import numpy as np

    ncols = 3
    nrows = int(np.ceil(len(available) / ncols))
    figure, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for index, column in enumerate(available):
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        axes[index].boxplot(values, vert=True, showfliers=True, widths=0.5)
        axes[index].set_title(column, fontsize=10)
        axes[index].set_yscale("symlog", linthresh=1.0)
        axes[index].grid(alpha=0.2)
        axes[index].set_xticks([])
    for index in range(len(available), len(axes)):
        axes[index].axis("off")

    figure.suptitle(title)
    figure.tight_layout()

    destination = _prepare_destination(path)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return destination
