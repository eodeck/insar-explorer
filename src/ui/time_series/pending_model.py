"""Zero-or-one-row projection model for the pending time-series record."""

from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QAbstractTableModel, QModelIndex, QSize, pyqtSignal

from ...qt_compat import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_VCENTER,
    DECORATION_ROLE,
    DISPLAY_ROLE,
    EDIT_ROLE,
    FONT_ROLE,
    FOREGROUND_ROLE,
    HORIZONTAL,
    ITEM_IS_EDITABLE,
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    TEXT_ALIGNMENT_ROLE,
    TOOLTIP_ROLE,
)
from .columns import (
    TIME_SERIES_COLUMN_COUNT,
    TimeSeriesColumn,
)


class PendingTimeSeriesModel(QAbstractTableModel):
    """Project one immutable pending record without owning session state."""

    labelEdited = pyqtSignal(str)

    _HEADERS = {
        TimeSeriesColumn.LABEL: "Label",
        TimeSeriesColumn.TARGET: "T",
        TimeSeriesColumn.REFERENCE: "R",
    }
    _HEADER_TOOLTIPS = {
        TimeSeriesColumn.LABEL: "Pending time-series label",
        TimeSeriesColumn.TARGET: "Target type",
        TimeSeriesColumn.REFERENCE: "Reference type",
    }
    _TARGET_RESOURCES = {
        "point": ":/icons/icons/select_point.svg",
        "polygon": ":/icons/icons/polygon_selection.png",
    }
    _REFERENCE_RESOURCES = {
        "point": ":/icons/icons/select_select_reference.svg",
        "polygon": ":/icons/icons/polygon_reference_selection.png",
    }

    def __init__(self, parent=None):
        """Create an empty projection model."""
        super(PendingTimeSeriesModel, self).__init__(parent)
        self._record = None

    def rowCount(self, parent=QModelIndex()):
        """Return zero or one projected row."""
        return 0 if parent.isValid() or self._record is None else 1

    def columnCount(self, parent=QModelIndex()):
        """Return the fixed Label/Target/Reference schema."""
        return 0 if parent.isValid() else TIME_SERIES_COLUMN_COUNT

    def set_record(self, record):
        """Replace the projected snapshot without emitting edit intent."""
        self.beginResetModel()
        self._record = record
        self.endResetModel()

    def clear(self):
        """Project no pending record."""
        self.set_record(None)

    def record(self):
        """Return the currently projected snapshot for diagnostics/tests."""
        return self._record

    def data(self, index, role=DISPLAY_ROLE):
        """Return data for the single pending row."""
        if not index.isValid() or self._record is None or index.row() != 0:
            return None
        column = TimeSeriesColumn(index.column())
        if column == TimeSeriesColumn.LABEL:
            label = self._record.presentation.label or ""
            if role == DISPLAY_ROLE:
                return label or "Unnamed"
            if role == EDIT_ROLE:
                return label
            if not label and role == FONT_ROLE:
                font = QtGui.QFont()
                font.setItalic(True)
                return font
            if not label and role == FOREGROUND_ROLE:
                return QtGui.QBrush(self._placeholder_colour())
            if role == TOOLTIP_ROLE:
                return "Double-click to edit label"
            if role == TEXT_ALIGNMENT_ROLE:
                return ALIGN_LEFT | ALIGN_VCENTER
            return None

        selection = (
            self._record.target
            if column == TimeSeriesColumn.TARGET
            else self._record.reference
        )
        prefix = "Target" if column == TimeSeriesColumn.TARGET else "Reference"
        kind = self._selection_kind_value(selection)
        if role == DECORATION_ROLE:
            resource = self._resource_for(column, kind)
            if resource is not None:
                return QtGui.QIcon(resource)
            return None
        if role == DISPLAY_ROLE and column == TimeSeriesColumn.REFERENCE:
            return "Data" if kind in {"source", "source_data", "data"} else None
        if role == TOOLTIP_ROLE:
            return self._tooltip(prefix, kind)
        if role == TEXT_ALIGNMENT_ROLE:
            return ALIGN_CENTER
        return None

    def headerData(self, section, orientation, role=DISPLAY_ROLE):
        """Return compact headers and explanatory tooltips."""
        if orientation != HORIZONTAL or not 0 <= section < TIME_SERIES_COLUMN_COUNT:
            return None
        column = TimeSeriesColumn(section)
        if role == DISPLAY_ROLE:
            return self._HEADERS[column]
        if role == TOOLTIP_ROLE:
            return self._HEADER_TOOLTIPS[column]
        if role == TEXT_ALIGNMENT_ROLE:
            return ALIGN_CENTER if column != TimeSeriesColumn.LABEL else ALIGN_LEFT
        return None

    def flags(self, index):
        """Make only the Label cell editable."""
        if not index.isValid() or self._record is None:
            return ITEM_IS_ENABLED
        flags = ITEM_IS_ENABLED
        if index.column() == TimeSeriesColumn.LABEL:
            flags |= ITEM_IS_SELECTABLE
            flags |= ITEM_IS_EDITABLE
        return flags

    def setData(self, index, value, role=EDIT_ROLE):
        """Validate a label edit and emit controller intent."""
        if (
            role != EDIT_ROLE
            or self._record is None
            or not index.isValid()
            or index.row() != 0
            or index.column() != TimeSeriesColumn.LABEL
        ):
            return False
        normalized = str(value).strip()
        current = self._record.presentation.label or ""
        if normalized == current:
            return True
        self.labelEdited.emit(normalized)
        return True

    @staticmethod
    def _placeholder_colour():
        """Return palette-aware secondary text for an empty stored label."""
        palette = QtGui.QGuiApplication.palette()
        role_enum = getattr(QtGui.QPalette, "ColorRole", QtGui.QPalette)
        role = getattr(role_enum, "PlaceholderText", role_enum.Text)
        return palette.color(role)

    @classmethod
    def _resource_for(cls, column, kind):
        resources = (
            cls._TARGET_RESOURCES
            if column == TimeSeriesColumn.TARGET
            else cls._REFERENCE_RESOURCES
        )
        return resources.get(kind)

    @staticmethod
    def _tooltip(prefix, kind):
        if kind is None:
            return f"{prefix}: none"
        if prefix == "Reference" and kind in {"source", "source_data", "data"}:
            return "Reference: source data"
        if kind in {"point", "polygon"}:
            return f"{prefix}: {kind}"
        return f"{prefix}: unknown"

    @staticmethod
    def _selection_kind_value(selection):
        if selection is None:
            return None
        kind = getattr(selection, "kind", None)
        value = getattr(kind, "value", kind)
        return value if isinstance(value, str) else None
