"""Shared column language for time-series record item views."""

from enum import IntEnum


class TimeSeriesColumn(IntEnum):
    """Columns shared by pending and future committed time-series views."""

    LABEL = 0
    TARGET = 1
    REFERENCE = 2


TIME_SERIES_COLUMN_COUNT = len(TimeSeriesColumn)
from .presentation import (
    PENDING_ACTION_BUTTON_SIZE, PENDING_ACTION_ICON_SIZE,
    TIME_SERIES_ROW_HEIGHT, TIME_SERIES_TYPE_COLUMN_WIDTH,
    TIME_SERIES_TYPE_ICON_SIZE,
)

PENDING_ROW_HEIGHT = TIME_SERIES_ROW_HEIGHT
