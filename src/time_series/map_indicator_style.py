"""Shared semantic presentation defaults for time-series map indicators."""

from typing import Optional

from qgis.PyQt.QtGui import QColor

REFERENCE_INDICATOR_COLOR = QColor(220, 45, 45)
TARGET_INDICATOR_COLOR = QColor(0, 190, 230)
POINT_INDICATOR_OUTER_COLOR = QColor(0, 0, 0)
POINT_INDICATOR_TRANSPARENT_FILL = QColor(0, 0, 0, 0)

PENDING_POINT_OUTER_SIZE = 10
PENDING_POINT_INNER_SIZE = 9
COMMITTED_POINT_OUTER_SIZE = 9
COMMITTED_POINT_INNER_SIZE = 8
PENDING_POINT_PEN_WIDTH = 2
COMMITTED_POINT_PEN_WIDTH = 2

PENDING_LINE_WIDTH = 2
COMMITTED_LINE_WIDTH = 1
PENDING_FILL_ALPHA = 42
COMMITTED_FILL_ALPHA = 18
PENDING_COLOR_ALPHA = 235
COMMITTED_COLOR_ALPHA = 145
COMMITTED_COLOR_ALPHA_WHILE_PENDING = 95


def semantic_indicator_color(role: str, *, alpha: Optional[int] = None) -> QColor:
    """Return a detached target/reference color for safe caller mutation."""
    color = QColor(
        TARGET_INDICATOR_COLOR if role == "target" else REFERENCE_INDICATOR_COLOR
    )
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def point_indicator_outer_color(*, alpha: Optional[int] = None) -> QColor:
    """Return a detached black point-ring casing color."""
    color = QColor(POINT_INDICATOR_OUTER_COLOR)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def transparent_point_fill() -> QColor:
    """Return a detached fully transparent point-marker fill color."""
    return QColor(POINT_INDICATOR_TRANSPARENT_FILL)
