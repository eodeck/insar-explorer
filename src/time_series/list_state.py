"""Session-local metadata for committed time-series list presentation."""

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional, Tuple
from uuid import UUID


@dataclass(frozen=True)
class TimeSeriesListEntry:
    """List-only metadata for one committed record."""

    record_id: UUID
    sequence_number: int
    visible: bool = True


class TimeSeriesListState:
    """Own stable sequence numbers and visibility outside record storage."""

    def __init__(self) -> None:
        self._entries: Dict[UUID, TimeSeriesListEntry] = {}
        self._order = []
        self._next_sequence = 1

    def entries(self) -> Tuple[TimeSeriesListEntry, ...]:
        """Return entries in committed insertion order."""
        return tuple(self._entries[record_id] for record_id in self._order)

    def entry(self, record_id: UUID) -> Optional[TimeSeriesListEntry]:
        """Return metadata for one record UUID."""
        return self._entries.get(record_id)

    def add(self, record_id: UUID) -> TimeSeriesListEntry:
        """Allocate stable visible metadata for a newly committed record."""
        if record_id in self._entries:
            raise ValueError(f"committed list entry already exists: {record_id}")
        entry = TimeSeriesListEntry(record_id, self._next_sequence, True)
        self._next_sequence += 1
        self._entries[record_id] = entry
        self._order.append(record_id)
        return entry

    def remove(self, record_id: UUID) -> Optional[TimeSeriesListEntry]:
        """Remove list metadata without renumbering remaining entries."""
        entry = self._entries.pop(record_id, None)
        if entry is not None:
            self._order.remove(record_id)
        return entry

    def set_visible(self, record_id: UUID, visible: bool) -> bool:
        """Replace one entry visibility and report whether it changed."""
        entry = self._entries.get(record_id)
        if entry is None or entry.visible == bool(visible):
            return False
        self._entries[record_id] = replace(entry, visible=bool(visible))
        return True

    def set_all_visible(self, visible: bool) -> Tuple[UUID, ...]:
        """Set all entries and return UUIDs whose state changed."""
        changed = []
        for record_id in self._order:
            if self.set_visible(record_id, visible):
                changed.append(record_id)
        return tuple(changed)

    def visible_ids(self) -> Tuple[UUID, ...]:
        """Return visible record UUIDs in insertion order."""
        return tuple(entry.record_id for entry in self.entries() if entry.visible)

    def clear(self) -> None:
        """Clear session metadata and restart sequence allocation."""
        self._entries.clear()
        self._order.clear()
        self._next_sequence = 1
