"""Typed in-memory working state for one Map Settings layer context."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .range_defaults import RangePolicyDefaults
from .range_state import LayerRangeWorkingState
from .symbology_defaults import MapSymbologySettings


class MapSettingsProvenance(Enum):
    """Describe how one layer acquired ownership of its Map Settings state."""

    DEFAULT_INITIALIZED = "default_initialized"
    USER_EDITED = "user_edited"
    APPLIED = "applied"


@dataclass(frozen=True)
class MapSettingsDefaultFingerprint:
    """Immutable reusable defaults that initialized one untouched layer."""

    range_policy: RangePolicyDefaults
    symbology: MapSymbologySettings


@dataclass(frozen=True)
class LayerMapSettingsWorkingState:
    """Capture one layer's unapplied Map Settings editor state."""

    layer_id: str
    layer_type: int
    range_state: LayerRangeWorkingState
    reference_offset: float
    colormap_id: str
    colormap_reversed: bool
    symbology: MapSymbologySettings
    dirty: bool
    provenance: MapSettingsProvenance
    default_fingerprint: Optional[MapSettingsDefaultFingerprint]
