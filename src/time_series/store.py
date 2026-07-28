"""Ordered in-memory ownership for time-series records."""

from typing import Iterable, List, Optional, Tuple
from uuid import UUID

from ..models.time_series import TimeSeriesRecord


class TimeSeriesStore:
    """Own ordered time-series records and the active record identity."""

    def __init__(self) -> None:
        self._records: List[TimeSeriesRecord] = []
        self._active_id: Optional[UUID] = None

    def records(self) -> Tuple[TimeSeriesRecord, ...]:
        """Return records in display/render order."""
        return tuple(self._records)

    def active_record(self) -> Optional[TimeSeriesRecord]:
        """Return the active record, if any."""
        if self._active_id is None:
            return None
        return self.get(self._active_id)

    def active_id(self) -> Optional[UUID]:
        """Return the active record UUID, if any."""
        return self._active_id

    def add(self, record: TimeSeriesRecord, *, make_active: bool = True) -> None:
        """Append a record and optionally make it active."""
        if self.get(record.id) is not None:
            raise ValueError(f"time-series record already exists: {record.id}")
        self._records.append(record)
        if make_active:
            self._active_id = record.id

    def get(self, record_id: UUID) -> Optional[TimeSeriesRecord]:
        """Return a record by stable UUID."""
        index = self.index_of(record_id)
        return None if index is None else self._records[index]

    def index_of(self, record_id: UUID) -> Optional[int]:
        """Return the ordered index for a UUID."""
        for index, record in enumerate(self._records):
            if record.id == record_id:
                return index
        return None

    def replace(self, record: TimeSeriesRecord) -> bool:
        """Replace a record with the same UUID without changing order."""
        index = self.index_of(record.id)
        if index is None:
            return False
        self._records[index] = record
        return True

    def replace_many(self, records: Iterable[TimeSeriesRecord]) -> None:
        """Replace matching records by UUID without reordering."""
        replacements = {record.id: record for record in records}
        for index, current in enumerate(self._records):
            replacement = replacements.get(current.id)
            if replacement is not None:
                self._records[index] = replacement

    def remove(self, record_id: UUID) -> Optional[TimeSeriesRecord]:
        """Remove and return a record by UUID."""
        index = self.index_of(record_id)
        if index is None:
            return None
        return self.remove_at(index)

    def remove_at(self, index: int = -1) -> Optional[TimeSeriesRecord]:
        """Remove and return a record by ordered index."""
        if not self._records:
            return None
        try:
            normalized_index = index if index >= 0 else len(self._records) + index
            removed = self._records.pop(index)
        except IndexError:
            return None
        if removed.id == self._active_id:
            if not self._records:
                self._active_id = None
            elif normalized_index < len(self._records):
                self._active_id = self._records[normalized_index].id
            else:
                self._active_id = self._records[-1].id
        return removed

    def set_active(self, record_id: Optional[UUID]) -> None:
        """Set the active record using UUID identity."""
        if record_id is None:
            self._active_id = None
            return
        if self.get(record_id) is None:
            raise KeyError(f"time-series record not found: {record_id}")
        self._active_id = record_id

    def clear(self) -> None:
        """Remove all records and clear active identity."""
        self._records.clear()
        self._active_id = None
