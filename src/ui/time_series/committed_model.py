"""Qt projection model for committed time-series records and list metadata."""

from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QAbstractTableModel, QModelIndex, pyqtSignal

from ...qt_compat import (
    ALIGN_CENTER, ALIGN_LEFT, ALIGN_VCENTER, CHECK_STATE_ROLE, CHECKED,
    DECORATION_ROLE, DISPLAY_ROLE, EDIT_ROLE, FONT_ROLE, FOREGROUND_ROLE,
    HORIZONTAL, ITEM_IS_EDITABLE, ITEM_IS_ENABLED, ITEM_IS_SELECTABLE,
    ITEM_IS_USER_CHECKABLE, TEXT_ALIGNMENT_ROLE, TOOLTIP_ROLE, UNCHECKED,
)
from .committed_columns import COMMITTED_COLUMN_COUNT, CommittedTimeSeriesColumn
from .presentation import (
    SOURCE_REFERENCE_KINDS, optional_label_display, placeholder_colour,
    resource_for_selection, selection_kind_value, selection_tooltip,
)


class CommittedTimeSeriesModel(QAbstractTableModel):
    """Project list metadata and resolve immutable records through a provider."""

    visibilityEdited = pyqtSignal(object, bool)
    labelEdited = pyqtSignal(object, str)

    _HEADERS = {
        CommittedTimeSeriesColumn.VISIBLE: "",
        CommittedTimeSeriesColumn.SEQUENCE: "No",
        CommittedTimeSeriesColumn.LABEL: "Label",
        CommittedTimeSeriesColumn.TARGET: "T",
        CommittedTimeSeriesColumn.REFERENCE: "R",
    }
    _HEADER_TOOLTIPS = {
        CommittedTimeSeriesColumn.VISIBLE: "Show or hide all time series",
        CommittedTimeSeriesColumn.SEQUENCE: "Time-series sequence number",
        CommittedTimeSeriesColumn.LABEL: "Time-series label",
        CommittedTimeSeriesColumn.TARGET: "Target selection type",
        CommittedTimeSeriesColumn.REFERENCE: "Reference selection type",
    }

    def __init__(self, list_state, record_provider, parent=None):
        """Create a read-only projection over authoritative state providers."""
        super(CommittedTimeSeriesModel, self).__init__(parent)
        self._list_state = list_state
        self._record_provider = record_provider

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._list_state.entries())

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else COMMITTED_COLUMN_COUNT

    def refresh(self):
        """Reset projection after an authoritative list/store transition."""
        self.beginResetModel()
        self.endResetModel()

    def entry_at(self, row):
        entries = self._list_state.entries()
        return entries[row] if 0 <= row < len(entries) else None

    def record_id_at(self, row):
        entry = self.entry_at(row)
        return None if entry is None else entry.record_id

    def row_for_id(self, record_id):
        for row, entry in enumerate(self._list_state.entries()):
            if entry.record_id == record_id:
                return row
        return None

    def visibility_summary(self):
        """Return immutable aggregate visibility without exposing list state."""
        entries = self._list_state.entries()
        return len(entries), sum(1 for entry in entries if entry.visible)

    def data(self, index, role=DISPLAY_ROLE):
        if not index.isValid():
            return None
        entry = self.entry_at(index.row())
        if entry is None:
            return None
        record = self._record_provider(entry.record_id)
        if record is None:
            return None
        column = CommittedTimeSeriesColumn(index.column())
        if column == CommittedTimeSeriesColumn.VISIBLE:
            if role == CHECK_STATE_ROLE:
                return CHECKED if entry.visible else UNCHECKED
            if role == TOOLTIP_ROLE:
                return "Show or hide this time series"
            if role == TEXT_ALIGNMENT_ROLE:
                return ALIGN_CENTER
            return None
        if column == CommittedTimeSeriesColumn.SEQUENCE:
            if role == DISPLAY_ROLE:
                return entry.sequence_number
            if role == TEXT_ALIGNMENT_ROLE:
                return ALIGN_CENTER
            return None
        if column == CommittedTimeSeriesColumn.LABEL:
            label = record.presentation.label or ""
            if role == DISPLAY_ROLE:
                return optional_label_display(label)
            if role == EDIT_ROLE:
                return label
            if role == TOOLTIP_ROLE:
                guidance = "Press F2 or use Rename to edit the label"
                if record.source is None or not record.source.layer_name:
                    return guidance
                return f"Source layer: {record.source.layer_name}\n{guidance}"
            if role == TEXT_ALIGNMENT_ROLE:
                return ALIGN_LEFT | ALIGN_VCENTER
            if not label and role == FONT_ROLE:
                font = QtGui.QFont()
                font.setItalic(True)
                return font
            if not label and role == FOREGROUND_ROLE:
                return QtGui.QBrush(placeholder_colour())
            return None
        selection = record.target if column == CommittedTimeSeriesColumn.TARGET else record.reference
        kind = selection_kind_value(selection)
        if role == DECORATION_ROLE:
            resource = resource_for_selection(
                target=column == CommittedTimeSeriesColumn.TARGET, kind=kind
            )
            return QtGui.QIcon(resource) if resource else None
        if role == DISPLAY_ROLE and column == CommittedTimeSeriesColumn.REFERENCE:
            return "Data" if kind in SOURCE_REFERENCE_KINDS else None
        if role == TOOLTIP_ROLE:
            prefix = "Target" if column == CommittedTimeSeriesColumn.TARGET else "Reference"
            return selection_tooltip(prefix, kind)
        if role == TEXT_ALIGNMENT_ROLE:
            return ALIGN_CENTER
        return None

    def headerData(self, section, orientation, role=DISPLAY_ROLE):
        if orientation != HORIZONTAL or not 0 <= section < COMMITTED_COLUMN_COUNT:
            return None
        column = CommittedTimeSeriesColumn(section)
        if role == DISPLAY_ROLE:
            return self._HEADERS[column]
        if role == TOOLTIP_ROLE:
            return self._HEADER_TOOLTIPS[column]
        if role == TEXT_ALIGNMENT_ROLE:
            return ALIGN_LEFT if column == CommittedTimeSeriesColumn.LABEL else ALIGN_CENTER
        return None

    def flags(self, index):
        if not index.isValid() or self.entry_at(index.row()) is None:
            return ITEM_IS_ENABLED
        flags = ITEM_IS_ENABLED | ITEM_IS_SELECTABLE
        column = CommittedTimeSeriesColumn(index.column())
        if column == CommittedTimeSeriesColumn.VISIBLE:
            flags |= ITEM_IS_USER_CHECKABLE
        elif column == CommittedTimeSeriesColumn.LABEL:
            flags |= ITEM_IS_EDITABLE
        return flags

    def setData(self, index, value, role=EDIT_ROLE):
        if not index.isValid():
            return False
        entry = self.entry_at(index.row())
        if entry is None:
            return False
        column = CommittedTimeSeriesColumn(index.column())
        if column == CommittedTimeSeriesColumn.VISIBLE and role == CHECK_STATE_ROLE:
            self.visibilityEdited.emit(entry.record_id, value == CHECKED)
            return True
        if column == CommittedTimeSeriesColumn.LABEL and role == EDIT_ROLE:
            self.labelEdited.emit(entry.record_id, str(value).strip())
            return True
        return False
