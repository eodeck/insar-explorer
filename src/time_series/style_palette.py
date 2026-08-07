"""Shared qualitative palettes and narrow color updates for time-series presentation."""

from dataclasses import replace


DISTINCT_TIME_SERIES_COLORS = (
    # Saturated / primary tab10 group first.
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan

    # Lighter tab20 companions second.
    "#aec7e8",  # light blue
    "#ffbb78",  # light orange
    "#98df8a",  # light green
    "#ff9896",  # light red
    "#c5b0d5",  # light purple
    "#c49c94",  # light brown
    "#f7b6d2",  # light pink
    "#c7c7c7",  # light gray
    "#dbdb8d",  # light olive
    "#9edae5",  # light cyan
)


def with_primary_series_color(record, color):
    """Return ``record`` with only coupled primary marker/line colors changed."""
    series = replace(
        record.presentation.series,
        marker_color=color,
        line_color=color,
    )
    return replace(
        record,
        presentation=replace(record.presentation, series=series),
    )
