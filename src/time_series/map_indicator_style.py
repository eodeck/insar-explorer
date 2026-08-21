"""Shared semantic presentation defaults for time-series map indicators."""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtGui import QColor

from .map_indicator_settings import POINT_SIZE_MAX, POINT_SIZE_MIN

POINT_INDICATOR_TRANSPARENT_FILL = QColor(0, 0, 0, 0)

PENDING_POINT_PEN_WIDTH = 2
COMMITTED_POINT_PEN_WIDTH = 2

PENDING_LINE_WIDTH = 2
COMMITTED_LINE_WIDTH = 1
PENDING_FILL_ALPHA = 90
COMMITTED_FILL_ALPHA = 60
PENDING_COLOR_ALPHA = 255
COMMITTED_COLOR_ALPHA = 200
COMMITTED_COLOR_ALPHA_WHILE_PENDING = 95

_CURRENT_BOX_PADDING = 6
_RECORD_MARKER_REDUCTION = 2
_MIN_RECORD_MARKER_SIZE = 1


@dataclass(frozen=True)
class PointIndicatorSizes:
    """Derived current-selection and record point-marker sizes."""

    current_marker: int
    current_box: int
    record_marker: int


def derive_point_indicator_sizes(point_size: int) -> PointIndicatorSizes:
    """Return clamped point-marker sizes derived from one global base size."""
    base = max(POINT_SIZE_MIN, min(POINT_SIZE_MAX, int(point_size)))
    return PointIndicatorSizes(
        current_marker=base,
        current_box=base + _CURRENT_BOX_PADDING,
        record_marker=max(base - _RECORD_MARKER_REDUCTION, _MIN_RECORD_MARKER_SIZE),
    )


def semantic_indicator_color(role: str, settings, *, alpha: Optional[int] = None) -> QColor:
    """Return a detached configured target/reference color."""
    color = QColor(settings.target_color if role == "target" else settings.reference_color)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def transparent_point_fill() -> QColor:
    """Return a detached fully transparent point-marker fill color."""
    return QColor(POINT_INDICATOR_TRANSPARENT_FILL)
