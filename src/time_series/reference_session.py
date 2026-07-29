"""Session-scoped reference selection for future time-series extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

from ..models.time_series import SpatialSelection


@dataclass(frozen=True)
class ActiveReference:
    """Immutable extraction snapshot retained for the current plugin session.

    The value object contains only renderer-independent input needed to apply
    the selected reference to future targets.  Record builders still create
    their own immutable ``SpatialSelection`` and numeric data snapshots.
    """

    dates: Tuple[Any, ...]
    values: Tuple[Tuple[float, ...], ...]
    selection: SpatialSelection

    @classmethod
    def create(cls, *, dates: Any, values: Any, selection: Any) -> "ActiveReference":
        """Normalize extracted reference input into an immutable snapshot."""
        normalized_selection = SpatialSelection.from_legacy(selection)
        if normalized_selection is None:
            raise ValueError("active reference requires a spatial selection")

        date_array = np.asarray(dates)
        value_array = np.asarray(values, dtype=float)
        if date_array.ndim != 1 or date_array.size == 0:
            raise ValueError("active reference dates must be a non-empty vector")
        if value_array.ndim == 1:
            value_array = value_array.reshape(-1, 1)
        if value_array.ndim != 2 or value_array.shape[0] != date_array.size:
            raise ValueError("active reference values must align with reference dates")

        return cls(
            dates=tuple(date_array.tolist()),
            values=tuple(tuple(float(value) for value in row) for row in value_array),
            selection=normalized_selection,
        )

    def values_array(self) -> np.ndarray:
        """Return a defensive numeric array for the extraction/build path."""
        return np.asarray(self.values, dtype=float)


class ActiveReferenceSession:
    """Own the explicit reference used by future records in one plugin session."""

    def __init__(self) -> None:
        self._active: Optional[ActiveReference] = None

    def current(self) -> Optional[ActiveReference]:
        """Return the current immutable reference snapshot, if selected."""
        return self._active

    def set(self, reference: ActiveReference) -> ActiveReference:
        """Replace the active reference after successful extraction."""
        if not isinstance(reference, ActiveReference):
            raise TypeError("reference must be an ActiveReference")
        self._active = reference
        return reference

    def clear(self) -> None:
        """Clear future-reference workflow state idempotently."""
        self._active = None
