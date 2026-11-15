from __future__ import annotations

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
