"""Session-scoped target selection for constructing pending records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

from ..models.time_series import SpatialSelection


@dataclass(frozen=True)
class CanonicalTargetSnapshot:
    """Immutable unreferenced target snapshot retained for the plugin session.

    Values are normalized into nested tuples, establishing a copy boundary from
    mutable extraction arrays. Reference operations never replace this snapshot.
    """

    dates: Tuple[Any, ...]
    values: Tuple[Tuple[float, ...], ...]
    selection: SpatialSelection
    plot_multiple: bool = False

    @classmethod
    def create(cls, *, dates: Any, values: Any, selection: Any, plot_multiple=False):
        """Normalize extracted target input into a renderer-independent snapshot."""
        normalized_selection = SpatialSelection.from_legacy(selection)
        if normalized_selection is None:
            raise ValueError("active target requires a spatial selection")
        date_array = np.asarray(dates)
        value_array = np.asarray(values, dtype=float)
        if date_array.ndim != 1 or date_array.size == 0:
            raise ValueError("active target dates must be a non-empty vector")
        if value_array.ndim == 1:
            value_array = value_array.reshape(-1, 1)
        if value_array.ndim != 2 or value_array.shape[0] != date_array.size:
            raise ValueError("active target values must align with target dates")
        return cls(
            dates=tuple(date_array.tolist()),
            values=tuple(tuple(float(value) for value in row) for row in value_array),
            selection=normalized_selection,
            plot_multiple=bool(plot_multiple),
        )

    def values_array(self):
        """Return a defensive numeric array for pending construction."""
        return np.asarray(self.values, dtype=float)


ActiveTarget = CanonicalTargetSnapshot


class ActiveTargetSession:
    """Own the latest target selection used to construct pending records."""

    def __init__(self):
        self._active: Optional[CanonicalTargetSnapshot] = None

    def current(self):
        """Return the canonical unreferenced target snapshot, if selected."""
        return self._active

    def set(self, target):
        """Replace the active target after successful extraction/rendering."""
        if not isinstance(target, CanonicalTargetSnapshot):
            raise TypeError("target must be a CanonicalTargetSnapshot")
        self._active = target
        return target

    def clear(self):
        """Clear target workflow state idempotently."""
        self._active = None
