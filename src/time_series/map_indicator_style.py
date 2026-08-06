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

_MIN_INNER_POINT_SIZE = 1
_MIN_OUTER_POINT_SIZE = 2


@dataclass(frozen=True)
class PointIndicatorSizes:
    """Derived pending and committed point-marker sizes."""

    pending_outer: int
    pending_inner: int
    committed_outer: int
    committed_inner: int


def derive_point_indicator_sizes(point_size: int) -> PointIndicatorSizes:
    """Return clamped point-marker sizes derived from one global base size."""
    base = max(POINT_SIZE_MIN, min(POINT_SIZE_MAX, int(point_size)))
    return PointIndicatorSizes(
        pending_outer=base,
        pending_inner=max(base - 2, _MIN_INNER_POINT_SIZE),
        committed_outer=max(base - 1, _MIN_OUTER_POINT_SIZE),
        committed_inner=max(base - 3, _MIN_INNER_POINT_SIZE),
    )


def semantic_indicator_color(role: str, settings, *, alpha: Optional[int] = None) -> QColor:
    """Return a detached configured target/reference color."""
    color = QColor(settings.target_color if role == "target" else settings.reference_color)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def point_indicator_outer_color(settings, *, alpha: Optional[int] = None) -> QColor:
    """Return a detached configured point-ring casing color."""
    color = QColor(settings.point_outer_color)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def transparent_point_fill() -> QColor:
    """Return a detached fully transparent point-marker fill color."""
    return QColor(POINT_INDICATOR_TRANSPARENT_FILL)
