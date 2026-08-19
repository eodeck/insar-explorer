"""Per-layer completed Target/Reference working state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .reference_session import ActiveReference
from .target_session import CanonicalTargetSnapshot


@dataclass(frozen=True)
class LayerSelectionWorkingState:
    """Completed active-layer selections retained for the plugin session."""

    target: Optional[CanonicalTargetSnapshot] = None
    reference: Optional[ActiveReference] = None
