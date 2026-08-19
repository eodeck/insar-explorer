"""Typed in-memory working state for one Map Settings layer context."""

from dataclasses import dataclass

from .range_state import LayerRangeWorkingState
from .symbology_defaults import MapSymbologySettings


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
