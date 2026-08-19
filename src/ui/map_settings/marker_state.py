"""Stable user-facing state for point-marker symbology controls."""

MARKER_SHAPES = (
    ("o", "circle", "Circle"),
    ("s", "square", "Square"),
    ("^", "triangle_up", "Triangle up"),
    ("v", "triangle_down", "Triangle down"),
    ("d", "diamond", "Diamond"),
    ("*", "star", "Star"),
)

DEFAULT_MARKER_SHAPE = "circle"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_OUTLINE_WIDTH_MM = 0.10

_MARKER_SHAPE_VALUES = frozenset(value for _, value, _ in MARKER_SHAPES)


def normalize_marker_shape(value):
    """Return one supported semantic marker value for persisted/user input."""
    value = str(value or "").strip().lower()
    return value if value in _MARKER_SHAPE_VALUES else DEFAULT_MARKER_SHAPE
