"""Shared column language for time-series record item views."""

from enum import IntEnum

from .presentation import TIME_SERIES_ROW_HEIGHT


class TimeSeriesColumn(IntEnum):
    """Columns shared by pending and future committed time-series views."""

    LABEL = 0
    TARGET = 1
    REFERENCE = 2


TIME_SERIES_COLUMN_COUNT = len(TimeSeriesColumn)

PENDING_ROW_HEIGHT = TIME_SERIES_ROW_HEIGHT
