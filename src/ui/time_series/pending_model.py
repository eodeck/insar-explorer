"""Zero-or-one-row projection model for the pending time-series record."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QAbstractTableModel, QModelIndex, QSize, pyqtSignal

from ...qt_compat import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_VCENTER,
    BACKGROUND_ROLE,
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
    PALETTE_ACTIVE,
    PALETTE_BASE,
    PALETTE_HIGHLIGHT,
)
from .columns import (
    TIME_SERIES_COLUMN_COUNT,
    TimeSeriesColumn,
)
from .presentation import (
    SOURCE_REFERENCE_KINDS, optional_label_display, placeholder_colour,
    resource_for_selection, selection_kind_value, selection_tooltip,
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


    def __init__(self, parent=None):
        """Create an empty projection model."""
        super(PendingTimeSeriesModel, self).__init__(parent)
        self._record = None
        self._toolbar_target_active = False

    def set_toolbar_target_active(self, active):
        """Render the pending row as the current toolbar target."""
        active = bool(active)
        if self._toolbar_target_active == active:
            return
        self._toolbar_target_active = active
        if self._record is not None:
            first = self.index(0, 0)
            last = self.index(0, TIME_SERIES_COLUMN_COUNT - 1)
            self.dataChanged.emit(first, last, [BACKGROUND_ROLE])

    def toolbar_target_is_active(self):
        """Return the presentation state for tests."""
        return self._toolbar_target_active

    @staticmethod
    def _blend_colour(foreground, background, emphasis=0.16):
        """Return a restrained palette-derived accent colour."""
        inverse = 1.0 - emphasis
        return QtGui.QColor(
            round(foreground.red() * emphasis + background.red() * inverse),
            round(foreground.green() * emphasis + background.green() * inverse),
            round(foreground.blue() * emphasis + background.blue() * inverse),
            background.alpha(),
        )

    def _toolbar_target_brush(self):
        palette = QtWidgets.QApplication.palette()
        highlight = palette.color(PALETTE_ACTIVE, PALETTE_HIGHLIGHT)
        base = palette.color(PALETTE_ACTIVE, PALETTE_BASE)
        return QtGui.QBrush(self._blend_colour(highlight, base))

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
        if role == BACKGROUND_ROLE and self._toolbar_target_active:
            return self._toolbar_target_brush()
        column = TimeSeriesColumn(index.column())
        if column == TimeSeriesColumn.LABEL:
            label = self._record.presentation.label or ""
            if role == DISPLAY_ROLE:
                return optional_label_display(label)
            if role == EDIT_ROLE:
                return label
            if not label and role == FONT_ROLE:
                font = QtGui.QFont()
                font.setItalic(True)
                return font
            if not label and role == FOREGROUND_ROLE:
                return QtGui.QBrush(placeholder_colour())
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
        kind = selection_kind_value(selection)
        if role == DECORATION_ROLE:
            resource = resource_for_selection(
                target=column == TimeSeriesColumn.TARGET, kind=kind
            )
            if resource is not None:
                return QtGui.QIcon(resource)
            return None
        if role == DISPLAY_ROLE and column == TimeSeriesColumn.REFERENCE:
            return "Data" if kind in SOURCE_REFERENCE_KINDS else None
        if role == TOOLTIP_ROLE:
            return selection_tooltip(prefix, kind)
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

