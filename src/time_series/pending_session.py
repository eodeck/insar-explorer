"""Session ownership for one uncommitted time-series record."""

from typing import Optional, TypeVar

from ..models.time_series import TimeSeriesRecord


_RecordT = TypeVar("_RecordT")


def resolve_editable_record(pending: Optional[_RecordT], committed: Optional[_RecordT]) -> Optional[_RecordT]:
    """Return pending ownership first, otherwise the active committed record."""
    return pending if pending is not None else committed


class PendingTimeSeriesSession:
    """Own the current uncommitted time-series record."""

    def __init__(self) -> None:
        self._record: Optional[TimeSeriesRecord] = None

    def record(self) -> Optional[TimeSeriesRecord]:
        """Return the pending record, if one exists."""
        return self._record

    def set(self, record: TimeSeriesRecord) -> None:
        """Store one complete pending record."""
        if not isinstance(record, TimeSeriesRecord):
            raise TypeError("record must be a TimeSeriesRecord")
        self._record = record

    def replace(self, record: TimeSeriesRecord) -> Optional[TimeSeriesRecord]:
        """Replace and return the previous pending record."""
        previous = self._record
        self.set(record)
        return previous

    def clear(self) -> Optional[TimeSeriesRecord]:
        """Clear and return the pending record; repeated calls are harmless."""
        previous = self._record
        self._record = None
        return previous
