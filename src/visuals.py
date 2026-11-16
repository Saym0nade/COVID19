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
