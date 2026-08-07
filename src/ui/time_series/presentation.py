"""Shared presentation helpers for pending and committed time-series views."""

from qgis.PyQt import QtGui

TIME_SERIES_ROW_HEIGHT = 20
TIME_SERIES_TYPE_COLUMN_WIDTH = 22
TIME_SERIES_TYPE_ICON_SIZE = 14
TIME_SERIES_ACTION_BUTTON_SIZE = 22
TIME_SERIES_ACTION_ICON_SIZE = 18

# Backward-compatible names used by the pending-row delegate/layout code.
PENDING_ACTION_BUTTON_SIZE = TIME_SERIES_ACTION_BUTTON_SIZE
PENDING_ACTION_ICON_SIZE = TIME_SERIES_ACTION_ICON_SIZE

TARGET_RESOURCES = {
    "point": ":/icons/icons/select_point.svg",
    "polygon": ":/icons/icons/polygon_selection.png",
}
REFERENCE_RESOURCES = {
    "point": ":/icons/icons/select_select_reference.svg",
    "polygon": ":/icons/icons/polygon_reference_selection.png",
}
SOURCE_REFERENCE_KINDS = {"source", "source_data", "data"}


def optional_label_display(label):
    """Return the visible label without mutating an empty stored value."""
    return label or "Unnamed"


def placeholder_colour():
    """Return palette-aware secondary text for an empty stored label."""
    palette = QtGui.QGuiApplication.palette()
    role_enum = getattr(QtGui.QPalette, "ColorRole", QtGui.QPalette)
    role = getattr(role_enum, "PlaceholderText", role_enum.Text)
    return palette.color(role)


def selection_kind_value(selection):
    """Return a defensive normalized kind string for a spatial selection."""
    if selection is None:
        return "none"
    kind = getattr(selection, "kind", None)
    kind = getattr(kind, "value", kind)
    return str(kind).strip().lower() if kind is not None else "unknown"


def resource_for_selection(*, target, kind):
    """Resolve the established target/reference resource without guessing."""
    return (TARGET_RESOURCES if target else REFERENCE_RESOURCES).get(kind)


def selection_tooltip(prefix, kind):
    """Return the semantic status tooltip for a selection kind."""
    if kind in SOURCE_REFERENCE_KINDS and prefix == "Reference":
        return "Reference: source data"
    if kind not in {"point", "polygon", "none"}:
        kind = "unknown"
    return f"{prefix}: {kind}"
