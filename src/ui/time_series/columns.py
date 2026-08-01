"""Shared column language for time-series record item views."""

from enum import IntEnum


class TimeSeriesColumn(IntEnum):
    """Columns shared by pending and future committed time-series views."""

    LABEL = 0
    TARGET = 1
    REFERENCE = 2


TIME_SERIES_COLUMN_COUNT = len(TimeSeriesColumn)
PENDING_ROW_HEIGHT = 24
TIME_SERIES_ROW_HEIGHT = PENDING_ROW_HEIGHT
TIME_SERIES_TYPE_COLUMN_WIDTH = 22
TIME_SERIES_TYPE_ICON_SIZE = 14
PENDING_ACTION_BUTTON_SIZE = 24
PENDING_ACTION_ICON_SIZE = 18
