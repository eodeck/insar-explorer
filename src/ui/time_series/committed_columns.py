"""Column schema and geometry for the committed time-series list."""

from enum import IntEnum


class CommittedTimeSeriesColumn(IntEnum):
    """Fixed committed-list column order."""

    VISIBLE = 0
    SEQUENCE = 1
    LABEL = 2
    TARGET = 3
    REFERENCE = 4


COMMITTED_COLUMN_COUNT = len(CommittedTimeSeriesColumn)
COMMITTED_VISIBLE_COLUMN_WIDTH = 24
COMMITTED_SEQUENCE_COLUMN_WIDTH = 38
