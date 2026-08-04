"""Shared semantic presentation defaults for time-series map indicators."""

from typing import Optional

from qgis.PyQt.QtGui import QColor

POINT_INDICATOR_TRANSPARENT_FILL = QColor(0, 0, 0, 0)

PENDING_POINT_OUTER_SIZE = 11
PENDING_POINT_INNER_SIZE = 9
COMMITTED_POINT_OUTER_SIZE = 11
COMMITTED_POINT_INNER_SIZE = 9
PENDING_POINT_PEN_WIDTH = 2
COMMITTED_POINT_PEN_WIDTH = 2

PENDING_LINE_WIDTH = 2
COMMITTED_LINE_WIDTH = 1
PENDING_FILL_ALPHA = 90
COMMITTED_FILL_ALPHA = 60
PENDING_COLOR_ALPHA = 255
COMMITTED_COLOR_ALPHA = 200
COMMITTED_COLOR_ALPHA_WHILE_PENDING = 95


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
